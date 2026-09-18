# 模块：seed.py —— 开发/演示用模拟数据播种脚本。
#
# 需求文档明确"可以有模拟数据"。本脚本插入 3 条流水线 + 6 条故障，
# 覆盖 pending / processing / done 三种状态，便于前端列表、筛选、详情、状态推进的联调与演示。
#
# 运行（在 backend/ 目录、激活 .venv 后）：
#     python seed.py
#
# 设计要点：
#   · 通过 crud 层写入（而非直接 db.add），让状态流转走真实业务规则
#     （done 必填 handling_note、done 不可逆等），保证 seed 数据与线上行为完全一致；
#   · 幂等：若已存在流水线则跳过，避免重复播种（需重播请先手动清空数据库）；
#   · 只"加"不做删表/清库等破坏性操作（遵循规则 2.7 / 3.5）。

from datetime import datetime, timedelta

from app import crud, schemas
from app.database import SessionLocal, init_models
from app.models import FaultStatus


def seed() -> None:
    """播种 3 条流水线 + 6 条故障（覆盖三种状态）。幂等：已有流水线则跳过。"""
    init_models()  # 表不存在则创建（可反复运行，不会改已存在的表）
    db = SessionLocal()
    try:
        # ---- 幂等保护：已有流水线就跳过，避免重复插入 ----
        existing = crud.list_pipelines(db)
        if existing:
            print(f"[skip] 已存在 {len(existing)} 条流水线，跳过播种（如需重播请先清空数据库文件）。")
            return

        # ---- 3 条流水线（主数据）----
        line_a = crud.create_pipeline(db, schemas.PipelineCreate(code="LINE-A", name="总装线A", description="底盘与总装"))
        line_b = crud.create_pipeline(db, schemas.PipelineCreate(code="LINE-B", name="焊接线B", description="车身焊接"))
        line_c = crud.create_pipeline(db, schemas.PipelineCreate(code="LINE-C", name="包装线C", description="下线包装"))
        print(f"[ok] 流水线：{line_a.code} / {line_b.code} / {line_c.code}")

        # 以"当前时间"为基准构造错落的发生时间，便于验证列表按 occurred_at 倒序展示。
        now = datetime.now()

        # ---- 6 条故障，覆盖三种状态与两条"完成"路径 ----
        # 1) LINE-A · pending：登记后不推进，停在待处理。
        crud.create_fault(db, schemas.FaultCreate(
            pipeline_id=line_a.id,
            location="3号工位传送带",
            occurred_at=now - timedelta(hours=2),
            symptom="传送带运行时有异响并偶发卡顿",
        ))

        # 2) LINE-A · processing：pending -> processing（note 可选，此处填派工说明）。
        f2 = crud.create_fault(db, schemas.FaultCreate(
            pipeline_id=line_a.id,
            location="5号工位机械臂",
            occurred_at=now - timedelta(hours=5),
            symptom="机械臂定位偏移，装配孔位对不准",
        ))
        crud.transition_fault(db, f2.id, FaultStatus.processing, "已派维修工排查编码器")

        # 3) LINE-B · done：pending -> processing -> done（完成必须带说明）。
        f3 = crud.create_fault(db, schemas.FaultCreate(
            pipeline_id=line_b.id,
            location="焊接机器人W2",
            occurred_at=now - timedelta(days=1),
            symptom="焊枪温度异常升高，触发过温报警",
        ))
        crud.transition_fault(db, f3.id, FaultStatus.processing, "停机降温，检查冷却水路")
        crud.transition_fault(db, f3.id, FaultStatus.done, "清洗冷却水路滤网并补充冷却液，温度恢复正常")

        # 4) LINE-B · pending：最近发生（40 分钟前），用于验证倒序时排在前列。
        crud.create_fault(db, schemas.FaultCreate(
            pipeline_id=line_b.id,
            location="上料区送料机构",
            occurred_at=now - timedelta(minutes=40),
            symptom="送料卡滞，板材无法自动进入焊接位",
        ))

        # 5) LINE-C · processing：pending -> processing。
        f5 = crud.create_fault(db, schemas.FaultCreate(
            pipeline_id=line_c.id,
            location="贴标机L1",
            occurred_at=now - timedelta(hours=8),
            symptom="标签贴附位置偏移，条码扫不出",
        ))
        crud.transition_fault(db, f5.id, FaultStatus.processing, "调整贴标头角度与光电传感器")

        # 6) LINE-C · done：pending -> done 直达（验证"不经处理中直接完成"这条路径，note 仍必填）。
        f6 = crud.create_fault(db, schemas.FaultCreate(
            pipeline_id=line_c.id,
            location="封箱机B3",
            occurred_at=now - timedelta(days=2),
            symptom="封箱胶带频繁断裂导致停线",
        ))
        crud.transition_fault(db, f6.id, FaultStatus.done, "更换胶带张力弹簧并清洁切刀，连续运行正常")

        # ---- 汇总：按状态统计，确认三态都有数据 ----
        faults, total = crud.list_faults(db, page=1, size=100)
        by_status = {s.value: 0 for s in FaultStatus}
        for f in faults:
            by_status[f.status.value] += 1
        print(f"[ok] 故障：共 {total} 条，状态分布 {by_status}")
        print("[done] 播种完成。启动后端后可在 http://127.0.0.1:8000/docs 或前端页面查看。")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
