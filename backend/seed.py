# 模块：seed.py —— 开发/演示用模拟数据播种脚本（第三阶段 M8 扩展）。
#
# 播种两块内容，各自独立幂等（重复执行不重复插入）：
#   ① 演示账号 ×5：2 普通用户 + 2 处理人员 + 1 管理员（需求二不开放自助注册，
#      账号只能由本脚本或管理员界面创建）；
#   ② 模拟数据：3 条流水线 + 5 条故障，覆盖 待处理(未指派)/处理中/待确认/已完成
#      四种状态与指派、改派、退回等闭环动作（前端 M6 三账号验收用）。
#
# 运行（在 backend/ 目录、激活 .venv 后）：
#     $env:SEED_PASSWORD="你的演示密码"; python seed.py        # PowerShell
#     SEED_PASSWORD=你的演示密码 python seed.py                 # bash
#
# 设计要点：
#   · 密码走环境变量 SEED_PASSWORD（≥6 位），不落代码、不入库明文（crud.create_user 内 bcrypt 哈希）；
#     仅当库中还缺少演示账号时才要求该变量——全部已存在则免变量直接跳过（幂等）；
#   · 账号幂等按 username 逐个判断：老库（只有流水线没有用户）再跑一次即可补上账号；
#   · 数据幂等沿用旧口径：已有流水线则跳过故障播种；
#   · 故障通过 crud 动作链写入（create→assign→start→submit→confirm…），
#     让状态机与时间线和线上行为完全一致，不直接改字段；
#   · 只"加"不做删表/清库等破坏性操作（遵循规则 2.6 / 2.7）。

import os
from datetime import datetime, timedelta

from app import crud, schemas
from app.database import SessionLocal, init_models
from app.models import FaultRole, FaultStatus, User

# 演示账号清单：(username, display_name, role)。密码统一取环境变量 SEED_PASSWORD。
DEMO_USERS: list[tuple[str, str, FaultRole]] = [
    ("reporter01", "报修人张三", FaultRole.user),
    ("reporter02", "报修人李四", FaultRole.user),
    ("handler01", "处理员王五", FaultRole.handler),
    ("handler02", "处理员赵六", FaultRole.handler),
    ("admin01", "管理员钱七", FaultRole.admin),
]


def seed_users(db) -> dict[str, User]:
    """逐个补齐缺失的演示账号，返回 username -> User 映射（含本次新建与库中已有）。"""
    users = {u.username: u for u in crud.list_users(db)}
    missing = [(n, d, r) for n, d, r in DEMO_USERS if n not in users]
    if missing:
        password = os.getenv("SEED_PASSWORD")
        if not password:
            raise SystemExit(
                "[abort] 库中缺少演示账号且未设置环境变量 SEED_PASSWORD（≥6 位）。\n"
                "        PowerShell 示例：$env:SEED_PASSWORD=\"passw0rd!\"; python seed.py"
            )
        for username, display_name, role in missing:
            user = crud.create_user(db, schemas.UserCreate(
                username=username, password=password, display_name=display_name, role=role,
            ))
            users[username] = user
            print(f"[ok] 账号：{user.username}（{user.display_name} / {user.role.value}）")
    else:
        print(f"[skip] {len(DEMO_USERS)} 个演示账号均已存在，跳过建号。")
    return users


def seed_data(db, users: dict[str, User]) -> None:
    """播种 3 条流水线 + 5 条闭环状态各异的故障。幂等：已有流水线则整体跳过。"""
    existing = crud.list_pipelines(db)
    if existing:
        print(f"[skip] 已存在 {len(existing)} 条流水线，跳过数据播种（如需重播请先清空数据库文件）。")
        return

    # ---- 3 条流水线（主数据）----
    line_a = crud.create_pipeline(db, schemas.PipelineCreate(code="LINE-A", name="总装线A", description="底盘与总装"))
    line_b = crud.create_pipeline(db, schemas.PipelineCreate(code="LINE-B", name="焊接线B", description="车身焊接"))
    line_c = crud.create_pipeline(db, schemas.PipelineCreate(code="LINE-C", name="包装线C", description="下线包装"))
    print(f"[ok] 流水线：{line_a.code} / {line_b.code} / {line_c.code}")

    admin, h1, h2 = users["admin01"], users["handler01"], users["handler02"]
    r1, r2 = users["reporter01"], users["reporter02"]
    now = datetime.now()

    def _mk(creator: User, pipeline, location: str, ago: timedelta, symptom: str):
        return crud.create_fault(db, schemas.FaultCreate(
            pipeline_id=pipeline.id, location=location,
            occurred_at=now - ago, symptom=symptom,
        ), creator=creator)

    # 1) pending · 未指派：验证管理员「指派」按钮与列表"未分派"筛选
    _mk(r1, line_a, "3号工位传送带", timedelta(hours=2), "传送带运行时有异响并偶发卡顿")

    # 2) processing：create → assign → start，处理中可追加进展
    f2 = _mk(r2, line_a, "5号工位机械臂", timedelta(hours=5), "机械臂定位偏移，装配孔位对不准")
    crud.assign_fault(db, f2.id, h1.id, actor=admin)
    crud.start_fault(db, f2.id, actor=h1)
    crud.add_progress(db, f2.id, "已现场确认编码器数据漂移，等待备件到货", actor=h1)

    # 3) awaiting_confirmation：完整走到「提交结果」，等创建人确认/退回
    f3 = _mk(r1, line_b, "焊接机器人W2", timedelta(days=1), "焊枪温度异常升高，触发过温报警")
    crud.assign_fault(db, f3.id, h2.id, actor=admin)
    crud.start_fault(db, f3.id, actor=h2)
    crud.submit_fault(db, f3.id, "清洗冷却水路滤网并补充冷却液，连续试运行两小时温度正常", actor=h2)

    # 4) done：提交 → 创建人确认 的完整闭环（含改派一段：h1 病假转 h2 前先给 h1）
    f4 = _mk(r2, line_c, "封箱机B3", timedelta(days=2), "封箱胶带频繁断裂导致停线")
    crud.assign_fault(db, f4.id, h1.id, actor=admin)
    crud.reassign_fault(db, f4.id, h2.id, "王五当日排班调整，转赵六跟进", actor=admin)
    crud.start_fault(db, f4.id, actor=h2)
    crud.submit_fault(db, f4.id, "更换胶带张力弹簧并清洁切刀，连续运行正常", actor=h2)
    crud.confirm_fault(db, f4.id, None, actor=r2)

    # 5) pending · 最近发生：验证倒序与「指派后未开始」形态
    f5 = _mk(r1, line_b, "上料区送料机构", timedelta(minutes=40), "送料卡滞，板材无法自动进入焊接位")
    crud.assign_fault(db, f5.id, h1.id, actor=admin)

    # ---- 汇总：按状态统计，确认四态都有数据 ----
    faults, total = crud.list_faults(db, viewer=admin, page=1, size=100)
    by_status = {s.value: 0 for s in FaultStatus}
    for f in faults:
        by_status[f.status.value] += 1
    print(f"[ok] 故障：共 {total} 条，状态分布 {by_status}")
    print("[done] 播种完成。启动后端后可在 http://127.0.0.1:8000/docs 或前端页面查看。")


def seed() -> None:
    """入口：先建表，再补账号（独立幂等），最后播数据。"""
    init_models()  # 表不存在则创建（可反复运行，不会改已存在的表）
    db = SessionLocal()
    try:
        users = seed_users(db)
        seed_data(db, users)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
