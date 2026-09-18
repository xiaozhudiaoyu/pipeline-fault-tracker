# 模块：CRUD 数据访问层 —— 所有数据库读写与业务规则校验集中在此。
#
# 分层职责（同 python_learn 的分层理念）：
#   routers/  —— 只管"接收请求、返回响应"，不写 SQL、不写业务判断；
#   crud.py   —— 管"怎么读写数据库 + 业务规则校验"，不碰 HTTP（异常由 exceptions.py 定义）；
#   models.py —— 管"表结构"。
#
# 为什么业务规则（状态流转校验）放 crud 而不是 router？
#   状态流转是核心业务规则，将来若有别的入口（脚本、定时任务）调用，规则应跟着数据层走，
#   不能只在 HTTP 层校验。放 crud 保证"无论从哪进来，规则都生效"。
#
# SQLAlchemy 2 查询风格：select() 构造语句，db.scalars()/db.scalar() 执行。
# 所有 db: Session 由路由层 Depends(get_db) 注入，本层不负责开关 session。

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import schemas
from .exceptions import (
    FaultNotFoundError,
    HandlingNoteRequiredError,
    InvalidTransitionError,
    PipelineCodeDuplicateError,
    PipelineNotFoundError,
)
from .models import FaultStatus, Pipeline, PipelineFault


# ── 流水线（主数据）──────────────────────────────────────────────────────
def list_pipelines(db: Session) -> list[Pipeline]:
    """返回全部流水线，按 code 升序（供前端筛选下拉与登记选择）。"""
    stmt = select(Pipeline).order_by(Pipeline.code)
    return list(db.scalars(stmt))


def get_pipeline(db: Session, pipeline_id: int) -> Pipeline:
    """按 ID 取流水线，不存在则抛 PipelineNotFoundError（404）。

    db.get() 是主键查询的快捷方式，命中 identity map 时不发 SQL。
    """
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise PipelineNotFoundError(pipeline_id)
    return pipeline


def create_pipeline(db: Session, data: schemas.PipelineCreate) -> Pipeline:
    """新增流水线，编码重复则抛 PipelineCodeDuplicateError（409）。"""
    # 先查编码唯一性，给出明确的业务错误（而非数据库层 IntegrityError 500）
    existing = db.scalar(select(Pipeline).where(Pipeline.code == data.code))
    if existing is not None:
        raise PipelineCodeDuplicateError(data.code)

    pipeline = Pipeline(**data.model_dump())
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)  # refresh 拿到数据库生成的 id / created_at
    return pipeline


# ── 故障记录（核心业务）──────────────────────────────────────────────────
def list_faults(
    db: Session,
    *,
    pipeline_id: int | None = None,
    status: FaultStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[PipelineFault], int]:
    """分页查询故障列表，返回 (当前页记录, 总数)。

    需求要点：
      · 按流水线、处理状态筛选（两个条件都可选，None 表示不限制）；
      · 默认按发生时间倒序（"列表默认优先展示最近发生的故障"）；
      · 分页返回 total，前端分页组件据此算总页数。

    selectinload(pipeline) 预加载关联流水线：
      FaultOut 需要嵌套 pipeline 字段，若懒加载则每条故障都会触发一次 SELECT（N+1 问题）。
      selectinload 用一条额外的 IN 查询把所有 pipeline 一次性加载，N 条故障只多 1 次查询。

    total 用独立的 count 查询：分页查询只取当前页，无法得知总数，必须单独 COUNT。
    两个查询共用同一套 where 条件，保证 total 与 items 的筛选口径一致。
    """
    # 数据查询（含预加载）与计数查询，分别构造但共用筛选条件
    stmt = select(PipelineFault).options(selectinload(PipelineFault.pipeline))
    count_stmt = select(func.count()).select_from(PipelineFault)

    if pipeline_id is not None:
        stmt = stmt.where(PipelineFault.pipeline_id == pipeline_id)
        count_stmt = count_stmt.where(PipelineFault.pipeline_id == pipeline_id)
    if status is not None:
        stmt = stmt.where(PipelineFault.status == status)
        count_stmt = count_stmt.where(PipelineFault.status == status)

    total = db.scalar(count_stmt) or 0
    # 排序 + 分页：occurred_at 倒序；offset 跳过前面页，limit 取本页
    stmt = stmt.order_by(PipelineFault.occurred_at.desc()).offset((page - 1) * size).limit(size)
    items = list(db.scalars(stmt))
    return items, total


def get_fault(db: Session, fault_id: int) -> PipelineFault:
    """按 ID 取故障详情（含预加载 pipeline），不存在则抛 FaultNotFoundError（404）。

    用 select + selectinload 而非 db.get：db.get 不会加载 relationship，
    而 FaultOut 需要 pipeline 嵌套字段，故统一走带预加载的查询。
    """
    stmt = (
        select(PipelineFault)
        .options(selectinload(PipelineFault.pipeline))
        .where(PipelineFault.id == fault_id)
    )
    # Session.scalar(stmt)：按主键至多命中一行，返回该 ORM 对象或 None（= execute(stmt).scalar()）。
    # 注意 Session 没有 scalar_one_or_none（那是 Result 的方法），此处与本文件 count 查询一致用 Session.scalar。
    fault = db.scalar(stmt)
    if fault is None:
        raise FaultNotFoundError(fault_id)
    return fault


def create_fault(db: Session, data: schemas.FaultCreate) -> PipelineFault:
    """登记新故障。

    业务规则：
      · pipeline_id 必须指向已存在的流水线（get_pipeline 校验，不存在抛 404）；
      · 新故障一律置为 pending —— 不接受客户端指定初始状态，防止绕过状态流转校验；
      · occurred_at 是用户填写的业务时间，created_at 由数据库 server_default 生成。

    返回前用 get_fault 重新查询：commit+refresh 后 pipeline 关联未加载，
    重新走带 selectinload 的查询，确保响应里 pipeline 字段完整。
    """
    get_pipeline(db, data.pipeline_id)  # 仅校验存在性，不存在会抛 PipelineNotFoundError
    fault = PipelineFault(
        pipeline_id=data.pipeline_id,
        location=data.location,
        occurred_at=data.occurred_at,
        symptom=data.symptom,
        status=FaultStatus.pending,  # 强制初始状态，忽略任何客户端传入
    )
    db.add(fault)
    db.commit()
    return get_fault(db, fault.id)


def transition_fault(
    db: Session,
    fault_id: int,
    target_status: FaultStatus,
    handling_note: str | None,
) -> PipelineFault:
    """推进故障状态 —— 本项目最核心的业务规则所在。

    需求原文："能够将故障从待处理推进至处理中、已完成，并补充和保存处理说明；
              完成处理时应有相应说明。后端应检查状态流转，已完成的记录不能直接恢复为待处理。"

    合法流转矩阵（行=当前状态，列=目标状态）：
        current \\ target | pending      | processing   | done
        ----------------|--------------|--------------|------------------
        pending         | ✗ 同状态     | ✓            | ✓（note 必填）
        processing      | ✓ 回退       | ✗ 同状态     | ✓（note 必填）
        done            | ✗ 不可逆     | ✗ 不可逆     | ✗ 同状态

    校验顺序（先拒非法，再查必填，最后执行）：
      1. 同状态变更无意义 → InvalidTransitionError（409）
      2. done 是终态，不可逆 → InvalidTransitionError（409）【需求硬性要求】
      3. 目标为 done 时 handling_note 必填 → HandlingNoteRequiredError（400）
      4. 其余（pending↔processing、*→done）合法，执行流转
    """
    fault = get_fault(db, fault_id)
    current = fault.status

    # 规则 1：同状态变更（如 pending → pending）无意义，拒绝
    if current == target_status:
        raise InvalidTransitionError(current.value, target_status.value)

    # 规则 2：done 是终态，不可逆 —— 需求明确"已完成的记录不能直接恢复为待处理"
    if current == FaultStatus.done:
        raise InvalidTransitionError(current.value, target_status.value)

    # 规则 3：完成处理必须有说明（需求"完成处理时应有相应说明"）
    # 注意 strip()：纯空格的 note 视同未填写，避免用 "   " 绕过校验
    if target_status == FaultStatus.done and (handling_note is None or not handling_note.strip()):
        raise HandlingNoteRequiredError()

    # ── 执行流转 ──
    fault.status = target_status
    # handling_note 为 None 表示"本次不改说明"（如 pending→processing 可只推进不填）；
    # 传了值就更新（含空串以外的有效说明）。
    if handling_note is not None:
        fault.handling_note = handling_note
    # closed_at：完成时写入"完成时刻"，回退（done 之外的目标）时清空
    if target_status == FaultStatus.done:
        fault.closed_at = datetime.now()
    else:
        fault.closed_at = None

    db.commit()
    # commit 触发了 updated_at 的 onupdate=func.now()；重新查询拿到含 pipeline 的完整对象
    return get_fault(db, fault_id)
