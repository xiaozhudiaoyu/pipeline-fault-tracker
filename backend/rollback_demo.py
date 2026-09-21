# 模块：rollback_demo.py —— D3 练习：多表写、中途失败需整体回滚的验证脚本。
#
# 练习背景（process/_next_week_plan.md · D3）：
#   加深对 SQLAlchemy Session / 事务 / 约束的理解：写一个「多表写、中途失败需整体回滚」的用例，
#   验证"第一步的写入不残留"。本脚本用三个场景从不同角度演示：
#     · 场景 1：数据库层报错（唯一约束冲突）触发回滚 —— 原子性主验证；
#     · 场景 2：业务层报错（模拟 crud 校验抛异常）触发回滚 —— 项目真实错误路径；
#     · 场景 3：commit 之后才失败 —— 展示事务边界（回滚救不了已提交的部分）。
#
# 运行（在 backend/ 目录、激活 .venv 后）：
#     python rollback_demo.py
#
# 设计要点：
#   · 用系统临时目录下的独立 SQLite 文件库，不碰 fault_tracker.db，脚本结束自动删除，项目目录零污染；
#   · echo=True 打开 SQL 回显，观察 BEGIN / INSERT / ROLLBACK / COMMIT 的先后顺序
#     （与 database.py 里 settings.db_echo 是同一个开关的用法）。

import os
import tempfile
from datetime import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Pipeline, PipelineFault

# 临时文件库：真实 SQLite 文件（想观察可停下脚本手动查看），跑完删除。
# 若上次运行异常残留了同名文件，先清掉，保证每次从零开始。
DB_PATH = os.path.join(tempfile.gettempdir(), "rollback_demo.db")
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

# engine / sessionmaker 创建方式与 database.py 保持一致，仅换库位置 + echo=True 便于观察 SQL。
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=True,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,  # 同 database.py：commit 后属性不过期，验证查询不触发多余 SELECT
    autoflush=False,         # 同 database.py：flush 时机显式控制，看清每步 SQL
)
Base.metadata.create_all(engine)


def count_rows(db: Session, model: type) -> int:
    """统计某张表的行数 —— 用全新查询验证"残留与否"，不依赖本事务的 pending 状态。"""
    return db.scalar(select(func.count()).select_from(model)) or 0


def scenario_1_integrity_error() -> None:
    """场景 1：同一事务里多步写，中途触发数据库层唯一约束冲突，整体回滚。

    步骤：写 pipeline（成功）→ 写 fault（成功）→ 再写 code 重复的 pipeline（flush 抛 IntegrityError）。
    回滚后前两步的写入应一并撤销 —— 事务原子性的主验证。
    """
    print("\n===== 场景 1：数据库层报错（唯一约束冲突）→ 整体回滚 =====")
    db = SessionLocal()
    try:
        # 第一步：登记一条流水线（本事务第一笔写；flush 发出 INSERT，事务尚未提交）
        pipeline = Pipeline(code="TEMP-LINE", name="回滚演示线")
        db.add(pipeline)
        db.flush()  # INSERT 成功，pipeline.id 由数据库自增生成

        # 第二步（关联表写入）：登记一条故障挂在它下面
        db.add(PipelineFault(
            pipeline_id=pipeline.id,
            location="演示工位",
            occurred_at=datetime.now(),
            symptom="回滚用例演示故障",
        ))
        db.flush()  # 故障 INSERT 也成功（仍在同一事务内，未提交）

        # 第三步：再写一条 code 重复的流水线 —— flush 时数据库层抛 IntegrityError
        db.add(Pipeline(code="TEMP-LINE", name="重复编码流水线"))
        db.flush()  # ← UNIQUE constraint failed，事务进入失败状态
        db.commit()  # 执行不到
    except IntegrityError as exc:
        print(f"[模拟失败] 第三步触发：{exc.orig}")
        db.rollback()  # 回滚整个事务：前两步成功的 INSERT 一并撤销
    finally:
        db.close()

    # 换一个全新 Session 查询（不依赖本事务的 pending 状态）
    check = SessionLocal()
    try:
        pipelines = count_rows(check, Pipeline)
        faults = count_rows(check, PipelineFault)
        print(f"[验证] 回滚后 pipelines={pipelines} 条（期望 0）、pipeline_faults={faults} 条（期望 0）")
        assert pipelines == 0 and faults == 0, "第一步的写入残留了！"
        print("[ok] 场景 1 通过：数据库层报错回滚后，第一步/第二步写入均无残留（事务原子性）")
    finally:
        check.close()


def scenario_2_business_error() -> None:
    """场景 2：业务校验失败（模拟 crud 层 raise）→ 显式 rollback，第一步不残留。

    对照 crud.py：业务规则校验失败时 raise exceptions 里的错误，crud 层本身没有显式 rollback，
    而是靠 get_db 的 finally db.close() 兜底回滚。本场景演示"显式 rollback"的等价写法，效果一致。
    """
    print("\n===== 场景 2：业务层报错（模拟 crud 校验失败）→ 显式 rollback =====")
    db = SessionLocal()
    try:
        db.add(Pipeline(code="TEMP-LINE-2", name="回滚演示线2"))
        db.flush()  # 第一步写成功（未提交）
        # 第二步"业务校验"失败：模拟 transition_fault 里 handling_note 必填等规则抛错
        raise ValueError("模拟业务规则校验失败（如：完成处理必须填写说明）")
        db.commit()  # 执行不到
    except ValueError as exc:
        print(f"[模拟失败] 业务校验抛错：{exc}")
        db.rollback()  # 显式回滚：撤销第一步的 INSERT
    finally:
        db.close()

    check = SessionLocal()
    try:
        pipelines = count_rows(check, Pipeline)
        print(f"[验证] 回滚后 pipelines={pipelines} 条（期望 0）")
        assert pipelines == 0, "第一步的写入残留了！"
        print("[ok] 场景 2 通过：业务异常回滚后，第一步写入无残留")
    finally:
        check.close()


def scenario_3_commit_boundary() -> None:
    """场景 3：第一步已 commit 之后第二步才失败 —— 展示事务边界。

    commit 是事务的终点：提交过的数据已成事实，之后的 rollback 救不回来。
    这正是 crud.py 里"先拒非法（校验），再执行提交（commit）"顺序的原因。
    """
    print("\n===== 场景 3：commit 之后才失败 → rollback 救不了已提交部分 =====")
    db = SessionLocal()
    try:
        pipeline = Pipeline(code="KEEP-LINE", name="已提交的流水线")
        db.add(pipeline)
        db.commit()  # 第一步独立提交 —— 事务结束，写入已成事实
        db.add(PipelineFault(
            pipeline_id=pipeline.id,
            location="演示工位2",
            occurred_at=datetime.now(),
            symptom="提交后失败的故障",
        ))
        db.flush()
        raise RuntimeError("第二步业务失败（此时故障 INSERT 已 flush 但未提交）")
    except RuntimeError as exc:
        print(f"[模拟失败] {exc}")
        db.rollback()  # 只能回滚 commit 之后的写入
    finally:
        db.close()

    check = SessionLocal()
    try:
        pipelines = count_rows(check, Pipeline)
        faults = count_rows(check, PipelineFault)
        print(f"[验证] rollback 后 pipelines={pipelines} 条（期望 1：已提交的回滚不掉）、"
              f"pipeline_faults={faults} 条（期望 0）")
        assert pipelines == 1 and faults == 0, "事务边界表现不符合预期！"
        print("[ok] 场景 3 通过：commit 是事务边界 —— 已提交的保留，未提交的回滚")
        # 清理：删掉演示数据（也顺带演示 ORM 层 cascade 删除）
        demo = check.scalar(select(Pipeline).where(Pipeline.code == "KEEP-LINE"))
        if demo is not None:
            check.delete(demo)
            check.commit()
        print(f"[清理] 演示数据已删除，pipelines={count_rows(check, Pipeline)} 条")
    finally:
        check.close()


if __name__ == "__main__":
    scenario_1_integrity_error()
    scenario_2_business_error()
    scenario_3_commit_boundary()
    # Windows 下 SQLite 文件被连接占用时无法删除，须先 dispose 释放连接池
    engine.dispose()
    os.remove(DB_PATH)
    print("\n[done] 三个场景全部通过，临时库文件已删除。")
