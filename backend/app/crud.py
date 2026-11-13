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

import os
import uuid
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from . import schemas, timeutil
from .config import settings
from .auth import (
    check_can_assign,
    check_can_confirm,
    check_can_priority_change,
    check_can_progress,
    check_can_reassign,
    check_can_return,
    check_can_start,
    check_can_submit,
    hash_password,
    verify_password,
)
from .exceptions import (
    AttachmentFormatError,
    AttachmentLimitError,
    AttachmentNotFoundError,
    AttachmentTooLargeError,
    FaultNotFoundError,
    HandlingNoteLockedError,
    HandlingNoteRequiredError,
    InvalidTransitionError,
    PermissionDeniedError,
    PipelineCodeDuplicateError,
    PipelineNotFoundError,
    TimelineNotFoundError,
    UserNotFoundError,
    UsernameDuplicateError,
)
from .models import (
    FaultAttachment,
    FaultPriority,
    FaultRole,
    FaultStatus,
    FaultTimeline,
    Pipeline,
    PipelineFault,
    TimelineAction,
    User,
)


def _viewer_filter(viewer: User) -> list:
    """根据登录角色返回默认视图的 where 条件列表（需求四.4）。

    admin: []—无过滤；
    handler: 分派给自己 或 自己创建；
    user: 仅自己创建。
    旧数据（created_by_id 与 assignee_id 均 NULL）不属任何人的视图，只有 admin 看到（需求六.2）。
    """
    if viewer.role == FaultRole.admin:
        return []
    if viewer.role == FaultRole.handler:
        return [or_(PipelineFault.assignee_id == viewer.id, PipelineFault.created_by_id == viewer.id)]
    return [PipelineFault.created_by_id == viewer.id]


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
    viewer: User,
    pipeline_id: int | None = None,
    status: FaultStatus | None = None,
    priority: FaultPriority | None = None,
    assignee_id: int | None = None,
    unassigned: bool = False,
    page: int = 1,
    size: int = 20,
) -> tuple[list[PipelineFault], int]:
    """分页查询故障列表（第三阶段：加入角色视图与负责人筛选）。

    viewer：当前登录用户；默认按角色过滤（见 _viewer_filter）。
    assignee_id / unassigned：需求四.4 “管理员可按负责人筛选、查看未指派”，
    对非 admin 也可用（与角色视图 AND 叠加，自然得到交集）。
    预加载 pipeline / created_by / assignee，FaultOut 嵌套字段不会触发 N+1。
    """
    stmt = (
        select(PipelineFault)
        .options(
            selectinload(PipelineFault.pipeline),
            selectinload(PipelineFault.created_by),
            selectinload(PipelineFault.assignee),
        )
    )
    count_stmt = select(func.count()).select_from(PipelineFault)

    conds: list = list(_viewer_filter(viewer))
    if pipeline_id is not None:
        conds.append(PipelineFault.pipeline_id == pipeline_id)
    if status is not None:
        conds.append(PipelineFault.status == status)
    if priority is not None:
        conds.append(PipelineFault.priority == priority)
    if assignee_id is not None:
        conds.append(PipelineFault.assignee_id == assignee_id)
    if unassigned:
        conds.append(PipelineFault.assignee_id.is_(None))
    for c in conds:
        stmt = stmt.where(c)
        count_stmt = count_stmt.where(c)

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(PipelineFault.occurred_at.desc()).offset((page - 1) * size).limit(size)
    items = list(db.scalars(stmt))
    return items, total


# 导出安全上限（防御性约束）：当前数据量远达不到，但避免未来数据增长后一次导出拖垮内存/浏览器
EXPORT_MAX_ROWS = 10000


def list_faults_for_export(
    db: Session,
    *,
    viewer: User,
    pipeline_id: int | None = None,
    status: FaultStatus | None = None,
    priority: FaultPriority | None = None,
    assignee_id: int | None = None,
    unassigned: bool = False,
    limit: int = EXPORT_MAX_ROWS,
) -> list[PipelineFault]:
    """导出用查询：口径与 list_faults 完全一致（含角色视图与负责人筛选），不分页 + 安全上限。"""
    stmt = (
        select(PipelineFault)
        .options(
            selectinload(PipelineFault.pipeline),
            selectinload(PipelineFault.created_by),
            selectinload(PipelineFault.assignee),
        )
    )
    conds: list = list(_viewer_filter(viewer))
    if pipeline_id is not None:
        conds.append(PipelineFault.pipeline_id == pipeline_id)
    if status is not None:
        conds.append(PipelineFault.status == status)
    if priority is not None:
        conds.append(PipelineFault.priority == priority)
    if assignee_id is not None:
        conds.append(PipelineFault.assignee_id == assignee_id)
    if unassigned:
        conds.append(PipelineFault.assignee_id.is_(None))
    for c in conds:
        stmt = stmt.where(c)
    stmt = stmt.order_by(PipelineFault.occurred_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def get_fault(db: Session, fault_id: int, viewer: User | None = None) -> PipelineFault:
    """按 ID 取故障详情（含预加载 pipeline / created_by / assignee），不存在抛 404。

    viewer 非 None 时执行 can_view_fault：无权限时与不存在同返回 404，不向低权限方
    泄露“这条存在但你看不到”。内部调用（如 create_fault 写完后重新加载）传 None。
    """
    stmt = (
        select(PipelineFault)
        .options(
            selectinload(PipelineFault.pipeline),
            selectinload(PipelineFault.created_by),
            selectinload(PipelineFault.assignee),
            # 第四阶段：FaultOut 内嵌 attachments，不预加载会让列表逐行懒加载 N+1
            #（uploader 关系自身 lazy=selectin，随 attachments 一并批量加载）。
            selectinload(PipelineFault.attachments),
        )
        .where(PipelineFault.id == fault_id)
    )
    fault = db.scalar(stmt)
    if fault is None:
        raise FaultNotFoundError(fault_id)
    if viewer is not None:
        from .auth import can_view_fault  # 局部导入避免循环

        if not can_view_fault(viewer, fault):
            raise FaultNotFoundError(fault_id)
    return fault


def _write_timeline(
    db: Session,
    fault: PipelineFault,
    action: TimelineAction,
    operator: User | None,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    from_assignee_id: int | None = None,
    to_assignee_id: int | None = None,
    note: str | None = None,
) -> FaultTimeline:
    """向 session 挂载一条时间线，**不 commit**——同事务由调用方末尾统一提交。

    需求四.2「状态更新与时间线插入在同一个 db.commit() 内」由此保证：任一处报错，
    外层 rollback 会让两者一起回到事务起点。operator=None 仅用于历史数据导入。

    返回新建的 entry（已 flush 拿到 id），供调用方（进展/提交附图）事后定位本条记录；
    不需要返回值的调用方直接忽略即可。flush 不会提交事务，回滚仍会连带撤销本次写入。
    """
    entry = FaultTimeline(
        fault_id=fault.id,
        action=action,
        operator_id=operator.id if operator is not None else None,
        operator_name_snapshot=operator.display_name if operator is not None else None,
        from_status=from_status,
        to_status=to_status,
        from_assignee_id=from_assignee_id,
        to_assignee_id=to_assignee_id,
        note=note,
    )
    db.add(entry)
    db.flush()
    return entry


def create_fault(db: Session, data: schemas.FaultCreate, *, creator: User) -> PipelineFault:
    """登记新故障（第三阶段：写入 created_by_id + create 时间线，同事务）。

    · pipeline_id 必须存在（get_pipeline 校验 → 404）；
    · 新故障一律 pending，不接受客户端指定初始状态；
    · created_by_id 取当前登录用户（**不接受**请求体传入，防伪造）；
    · db.flush() 取到 fault.id 但保持事务未提交，时间线挂 FK 后一起 commit。
    """
    get_pipeline(db, data.pipeline_id)
    fault = PipelineFault(
        pipeline_id=data.pipeline_id,
        location=data.location,
        occurred_at=data.occurred_at,
        symptom=data.symptom,
        status=FaultStatus.pending,
        priority=data.priority,
        created_by_id=creator.id,
    )
    db.add(fault)
    db.flush()
    _write_timeline(
        db, fault, TimelineAction.create, creator,
        to_status=FaultStatus.pending.value,
    )
    db.commit()
    return get_fault(db, fault.id)


def update_fault(
    db: Session, fault_id: int, data: schemas.FaultUpdate, *, viewer: User
) -> PipelineFault:
    """修改故障信息（第三阶段）：pending + (创建人本人 或 admin)，只落 location / symptom。

    与旧实现的差异：
      · priority 走 POST /{id}/priority 端点（需时间线记录）；
      · handling_note 由 submit 动作写入，PATCH 通道不再开放；
      · 状态门槛：pending 之外不可改（D6 保守：接手后需先退回）。
    不删旧 handling_note 锁定异常：旧错误码保留防止测试链射，仅本函数不再触发。
    """
    fault = get_fault(db, fault_id, viewer)
    if fault.status != FaultStatus.pending:
        raise InvalidTransitionError(current=fault.status.value, target="edit_basic")
    if viewer.role != FaultRole.admin and fault.created_by_id != viewer.id:
        raise PermissionDeniedError("仅创建人或管理员可修改基本信息，且仅限待处理状态")
    changes = data.model_dump(exclude_unset=True)
    # 只放行 location / symptom；传了 priority/handling_note 静默忽略（防旧客户端仍递交时造成 500）
    changes = {k: v for k, v in changes.items() if k in ("location", "symptom")}
    for field, value in changes.items():
        setattr(fault, field, value)
    db.commit()
    return get_fault(db, fault_id)


def _load_handler(db: Session, user_id: int) -> User:
    """assign/reassign 接手人校验：必须存在、角色 handler、且启用。"""
    assignee = db.get(User, user_id)
    if assignee is None or assignee.role != FaultRole.handler or not assignee.is_active:
        raise PermissionDeniedError("接手人必须是启用中的处理人员（handler）")
    return assignee


def assign_fault(db: Session, fault_id: int, assignee_id: int, *, actor: User) -> PipelineFault:
    """指派：pending + 无负责人 → 设定 assignee，状态不变。"""
    fault = get_fault(db, fault_id)
    check_can_assign(actor, fault)
    assignee = _load_handler(db, assignee_id)
    from_id = fault.assignee_id
    # 赋关系对象而非只写外键列 fault.assignee_id：本函数开头 get_fault 已用 selectinload
    # 把 assignee 关系加载为 None，SessionLocal 又是 expire_on_commit=False，commit 后属性
    # 不过期，末尾再 get_fault 命中 identity map 时 eager loader 不会覆盖这个「已加载」的
    # 关系 → 响应体会回 null 负责人（BUG-C，见 tests::TestAssignResponseAssignee）。
    # 走关系赋值同时同步 assignee_id 与关系本身，一次写入两条路径都对。
    fault.assignee = assignee
    _write_timeline(
        db, fault, TimelineAction.assign, actor,
        from_status=fault.status.value, to_status=fault.status.value,
        from_assignee_id=from_id, to_assignee_id=assignee.id,
    )
    db.commit()
    return get_fault(db, fault_id)


def reassign_fault(
    db: Session, fault_id: int, assignee_id: int, reason: str, *, actor: User
) -> PipelineFault:
    """改派：pending/processing + 现有负责人 → 新负责人，理由必填写入时间线。"""
    fault = get_fault(db, fault_id)
    check_can_reassign(actor, fault)
    assignee = _load_handler(db, assignee_id)
    from_id = fault.assignee_id
    # 同 assign_fault：赋关系对象，避免末尾重取时旧 assignee 关系不被覆盖（BUG-C）。
    fault.assignee = assignee
    _write_timeline(
        db, fault, TimelineAction.reassign, actor,
        from_status=fault.status.value, to_status=fault.status.value,
        from_assignee_id=from_id, to_assignee_id=assignee.id,
        note=reason,
    )
    db.commit()
    return get_fault(db, fault_id)


def start_fault(db: Session, fault_id: int, *, actor: User) -> PipelineFault:
    """开始处理：pending + 当前负责人 → processing。"""
    fault = get_fault(db, fault_id)
    check_can_start(actor, fault)
    from_status = fault.status
    fault.status = FaultStatus.processing
    _write_timeline(
        db, fault, TimelineAction.start, actor,
        from_status=from_status.value, to_status=FaultStatus.processing.value,
    )
    db.commit()
    return get_fault(db, fault_id)


def add_progress(db: Session, fault_id: int, note: str, *, actor: User) -> tuple[PipelineFault, int]:
    """追加进展：processing + 当前负责人；状态不变，进展写入时间线。

    返回 (故障, 本次新建的时间线 id)：后者供路由把 timeline_id 回给前端，
    前端据此走第二步向 /api/timelines/{id}/attachments 上传随附图片。
    """
    fault = get_fault(db, fault_id)
    check_can_progress(actor, fault)
    entry = _write_timeline(
        db, fault, TimelineAction.progress, actor,
        from_status=fault.status.value, to_status=fault.status.value,
        note=note,
    )
    db.commit()
    return get_fault(db, fault_id), entry.id


def submit_fault(
    db: Session, fault_id: int, result_note: str, *, actor: User
) -> tuple[PipelineFault, int]:
    """提交处理结果：processing + 当前负责人 → awaiting_confirmation；handling_note 一并写入。

    返回 (故障, 本次 submit 时间线 id)，口径同 add_progress（供附图两步式寻址）。
    """
    fault = get_fault(db, fault_id)
    check_can_submit(actor, fault)
    from_status = fault.status
    fault.status = FaultStatus.awaiting_confirmation
    fault.handling_note = result_note
    entry = _write_timeline(
        db, fault, TimelineAction.submit, actor,
        from_status=from_status.value, to_status=FaultStatus.awaiting_confirmation.value,
        note=result_note,
    )
    db.commit()
    return get_fault(db, fault_id), entry.id


def confirm_fault(
    db: Session, fault_id: int, reason: str | None, *, actor: User
) -> PipelineFault:
    """确认完成：awaiting_confirmation → done；admin 代确认时 reason 必填（需求 SM11）。"""
    fault = get_fault(db, fault_id)
    check_can_confirm(actor, fault)
    is_delegated = fault.created_by_id != actor.id
    if is_delegated and (reason is None or not reason.strip()):
        raise PermissionDeniedError("管理员代确认必须填写理由")
    from_status = fault.status
    fault.status = FaultStatus.done
    fault.closed_at = timeutil.business_now()
    _write_timeline(
        db, fault, TimelineAction.confirm, actor,
        from_status=from_status.value, to_status=FaultStatus.done.value,
        note=reason,
    )
    db.commit()
    return get_fault(db, fault_id)


def return_fault(db: Session, fault_id: int, reason: str, *, actor: User) -> PipelineFault:
    """退回处理：awaiting_confirmation → processing，理由必填写入时间线。

    原因非空白的校验在 schema 层（FaultReturnIn.reason strip 后 ≥2 字），不区分创建人
    自退与管理员代退回。对比：confirm_fault 另在 crud 层校 is_delegated 分支必填，
    因为那边的 reason 在 schema 里是选填（创建人本人确认无需备注）。
    """
    fault = get_fault(db, fault_id)
    check_can_return(actor, fault)
    from_status = fault.status
    fault.status = FaultStatus.processing
    _write_timeline(
        db, fault, TimelineAction.return_, actor,
        from_status=from_status.value, to_status=FaultStatus.processing.value,
        note=reason,
    )
    db.commit()
    return get_fault(db, fault_id)


def change_priority(
    db: Session, fault_id: int, priority: FaultPriority, *, actor: User
) -> PipelineFault:
    """优先级调整（AU9）：done 之前 admin 或创建人可调；不影响状态；记入时间线。"""
    fault = get_fault(db, fault_id)
    check_can_priority_change(actor, fault)
    old = fault.priority
    if old == priority:
        # 同值“调整”无意义但仍写入时间线（便于回溯“确认过”）；需求未定义拒绝，此处不抛错。
        pass
    fault.priority = priority
    _write_timeline(
        db, fault, TimelineAction.priority_change, actor,
        from_status=fault.status.value, to_status=fault.status.value,
        note=f"优先级 {old.value} → {priority.value}",
    )
    db.commit()
    return get_fault(db, fault_id)


def list_timelines(db: Session, fault_id: int, *, viewer: User) -> list[FaultTimeline]:
    """读取时间线：先走 can_view 检查（get_fault 内），按 created_at 升序返回。

    relationship 已配 order_by=FaultTimeline.created_at，直接取 fault.timelines。
    """
    fault = get_fault(db, fault_id, viewer)
    return list(fault.timelines)


# ── 图片附件（第四阶段）─────────────────────────────────────────────
# 存储口径（方案已定）：文件本体落 settings.upload_dir，库内只存元数据行；
# 数据 = 库文件 + uploads 目录两处，备份/迁移均须同时覆盖（README 11.5）。

# 文件头魔术字节 → (真实 MIME, 存储扩展名)。纯标准库判定，不引入 Pillow；
# 客户端声明的 content_type 与原始文件名一律不作数（可伪造，且中文名/路径分隔符不可信）。
_MAGIC_IMAGE_TYPES: list[tuple[bytes, str, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),   # PNG：8 字节签名
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),          # JPEG：SOI + 第三字节标记段
]

# 流式读写块大小：64 KB 够覆盖最长魔术字节（8B）百倍余量，又不把大文件一次吃进内存。
_UPLOAD_CHUNK = 64 * 1024


def _upload_dir() -> Path:
    """附件目录 Path，不存在则兜底 mkdir（照抄 database.ensure_sqlite_dir 风格）。

    每次调用都现读 settings.upload_dir：测试用 monkeypatch 改配置后无需重启进程；
    容器形态由 compose 注入 UPLOAD_DIR=/app/data/uploads（落 pft-data 卷）。
    """
    d = Path(settings.upload_dir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sniff_image(head: bytes) -> tuple[str, str]:
    """按文件头判定真实类型，返回 (mime, 扩展名)；非 PNG/JPEG 抛 AttachmentFormatError。"""
    for magic, mime, ext in _MAGIC_IMAGE_TYPES:
        if head.startswith(magic):
            return mime, ext
    raise AttachmentFormatError()


def list_attachments(db: Session, fault_id: int, viewer: User) -> list[FaultAttachment]:
    """附件列表：can_view 检查在 get_fault 内（无权与不存在同为 404），按上传时间正序。"""
    fault = get_fault(db, fault_id, viewer)
    return list(fault.attachments)


def add_attachment(db: Session, fault_id: int, upload, *, uploader: User) -> FaultAttachment:
    """保存一张随建故障上传的现场图片（upload 为 fastapi.UploadFile）。

    只登记 timeline_id=NULL 的现场图片；时间线附图走 add_attachment_for_timeline。
    权限沿 can_view_fault（get_fault 内），无权/不存在同为 404。
    """
    fault = get_fault(db, fault_id, uploader)
    return _register_image(db, fault, upload, uploader)


def add_attachment_for_timeline(
    db: Session, timeline_id: int, upload, *, uploader: User
) -> FaultAttachment:
    """向一条时间线记录（追加进展/提交结果）上传随附图片。

    权限（方案已定）：仅本条时间线的操作人本人或 admin 可附图（谁的动作谁的图），
    非归属 → 403；时间线不存在/所属故障不可见 → 404（不区分，防跨故障探测）。
    类型/大小/每条故障张数上限复用 _register_image（现场图片与附图共享每故障 ≤ 10 张预算）。
    """
    timeline = db.get(FaultTimeline, timeline_id)
    if timeline is None:
        raise TimelineNotFoundError(timeline_id)
    fault = timeline.fault
    from .auth import can_view_fault  # 局部导入避免循环（同 _can_view_attachment）
    if fault is None or not can_view_fault(uploader, fault):
        raise TimelineNotFoundError(timeline_id)
    if uploader.role != FaultRole.admin and timeline.operator_id != uploader.id:
        raise PermissionDeniedError("仅本条时间线的操作人或管理员可为其上传附图")
    return _register_image(db, fault, upload, uploader, timeline_id=timeline.id)


def _register_image(
    db: Session, fault: PipelineFault, upload, uploader: User, *, timeline_id: int | None = None
) -> FaultAttachment:
    """存一个上传图片文件并登记元数据（现场图片/时间线附图共用）。

    流程（方案已定，顺序不可颠倒）：
      ① 张数上限校验（count 现查本故障全部附图（含时间线），不信赖前端）；
      ② 流式落盘：边读边写边计数，超限中断并删半成品——不把整文件先读进内存；
        文件头在首块里 sniff，不合格同样删半成品后 422；
      ③ 入库 commit；入库失败回滚并删已落盘文件，防孤儿文件。
    存储文件名一律重写为 uuid4().hex + 真实扩展名，原始名只存字段供展示。
    timeline_id 为 None → 现场图片；非 None → 挂到对应时间线。
    """
    count = db.scalar(
        select(func.count()).select_from(FaultAttachment).where(FaultAttachment.fault_id == fault.id)
    ) or 0
    if count >= settings.attachment_max_per_fault:
        raise AttachmentLimitError(settings.attachment_max_per_fault)

    max_bytes = settings.attachment_max_bytes
    # 先写入同目录隐藏临时文件（同一文件系统，rename 原子），判定通过后才定名：
    # sniff 不过 / 超限 / 入库失败 → 删临时文件；成功 → os.replace 成正式名。
    upload_dir = _upload_dir()
    tmp_path = upload_dir / f".uploading-{uuid.uuid4().hex}"
    try:
        head = b""
        written = 0
        with open(tmp_path, "wb") as dst:
            while True:
                chunk = upload.file.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                if written + len(chunk) > max_bytes:
                    raise AttachmentTooLargeError(max_bytes)
                dst.write(chunk)
                if written == 0:
                    head = chunk[:12]  # 首块缓存文件头，最长魔术字节 8B 的 1.5 倍
                written += len(chunk)
        if written == 0:
            raise AttachmentFormatError()  # 空文件没有文件头，按格式不合法拦下
        content_type, ext = _sniff_image(head)
        filename = f"{uuid.uuid4().hex}{ext}"
        final_path = upload_dir / filename
        os.replace(tmp_path, final_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)  # 删半成品（已定名的不在本分支，无需回退）
        raise

    original = Path(upload.filename or "image").name  # 去路径化只留展示名，防目录穿越字符入库
    attachment = FaultAttachment(
        fault_id=fault.id,
        timeline_id=timeline_id,
        filename=filename,
        original_name=original[:255],
        content_type=content_type,
        size_bytes=written,
        uploader_id=uploader.id,
        uploader_name_snapshot=uploader.display_name,
    )
    db.add(attachment)
    try:
        db.commit()
    except Exception:
        # 入库失败：文件已落盘但库里没这行，不删就成了永远回放不到的孤儿 → 顺手清掉。
        db.rollback()
        final_path.unlink(missing_ok=True)
        raise
    db.refresh(attachment)
    return attachment


def get_attachment_for_download(db: Session, attachment_id: int, viewer: User) -> tuple[FaultAttachment, Path]:
    """取回放中的附件：权限沿所属故障的 can_view（无权与不存在同为 404）。

    库内元数据在但磁盘文件缺失（手工误删/卷未挂载）同样 404：
    对客户端而言“拿不到这张图”与“不存在”无需区分，话术统一不泄露内部状态。
    """
    attachment = db.get(FaultAttachment, attachment_id)
    if attachment is None:
        raise AttachmentNotFoundError(attachment_id)
    if not _can_view_attachment(viewer, attachment):
        raise AttachmentNotFoundError(attachment_id)
    path = _upload_dir() / attachment.filename
    if not path.is_file():
        raise AttachmentNotFoundError(attachment_id)
    return attachment, path


def _can_view_attachment(viewer: User, attachment: FaultAttachment) -> bool:
    """附件查看权 = 所属故障查看权（口径集中 auth.can_view_fault，本函数只是适配器）。

    读 attachment.fault 会触发懒加载；uploader 关系 lazy=selectin 已随 db.get 预加载。
    """
    from .auth import can_view_fault  # 局部导入避免循环（同 get_fault 既有写法）

    return can_view_fault(viewer, attachment.fault)


def delete_attachment(db: Session, attachment_id: int, viewer: User) -> None:
    """删除附件：镜像 update_fault 权限面（pending + 创建人/admin）→ 删库行 → 删文件。

    顺序取“先库后盘”：库行删失败文件还在（可重试）；若反过来先删文件后库失败，
    会留下“元数据在、本体无”的 404 幻行。文件不存在不报错（幂等，重复删可接受）。
    """
    attachment = db.get(FaultAttachment, attachment_id)
    if attachment is None:
        raise AttachmentNotFoundError(attachment_id)
    fault = attachment.fault
    if fault is None:  # FK CASCADE 下理论不可达，防御性兜底
        raise AttachmentNotFoundError(attachment_id)
    if fault.status != FaultStatus.pending:
        raise InvalidTransitionError(current=fault.status.value, target="attachment_delete")
    if viewer.role != FaultRole.admin and fault.created_by_id != viewer.id:
        raise PermissionDeniedError("仅创建人或管理员可删除附件，且仅限待处理状态")
    db.delete(attachment)
    db.commit()
    (_upload_dir() / attachment.filename).unlink(missing_ok=True)


# ── 用户（第三阶段）───────────────────────────────────────────────────
# 注：本层不包含 login 验证——verify_password 属于 auth.py（密码安全属于“认证”不属于“数据访问”）。
# authenticate() 只是个很薄的“查库 + 转交 auth.verify_password”组合，便于路由与 seed 统一调用。
# hash_password / verify_password 已提到文件顶部导入。


def get_user(db: Session, user_id: int) -> User:
    """按 ID 取用户，不存在抛 UserNotFoundError（404）。"""
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError(user_id)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    """登录/建用户时按唯一用户名查询。找不到返回 None（不抛，由调用方决定 401/409）。"""
    stmt = select(User).where(User.username == username)
    return db.scalars(stmt).first()


def list_users(db: Session) -> list[User]:
    """返回全部用户，按 username 升序（管理员管理页与指派下拉使用，M6 接入）。"""
    stmt = select(User).order_by(User.username)
    return list(db.scalars(stmt))


def create_user(db: Session, data: schemas.UserCreate) -> User:
    """创建用户。username 全表唯一，重复抛 UsernameDuplicateError（409）。

    不开放自助注册（需求二），本函数仅供：
      · M6 管理员接口 POST /api/users 调用；
      · M8 seed.py 初始化测试账号时调用。
    """
    if get_user_by_username(db, data.username) is not None:
        raise UsernameDuplicateError(data.username)
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        is_active=True,
        token_version=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    """登录验证：用户名存在 且 密码匹配 → 返回 User；否则 None。

    不检查 is_active——留给路由层区分“密码错”与“已停用”，
    避免向攻击者泄露“此用户名存在但已停用”这类信息。
    """
    user = get_user_by_username(db, username)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def bump_token_version(db: Session, user: User) -> User:
    """使当前用户的所有旧 token 立即失效。停用/改密/登出时调用（D3）。"""
    user.token_version += 1
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_user_active(db: Session, user: User, active: bool) -> User:
    """启用/停用账号。停用时顺手 bump token_version（需求二：停用后不能继续操作）。"""
    user.is_active = active
    if not active:
        user.token_version += 1
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user: User, new_password: str) -> User:
    """管理员重置密码：换哈希 + bump token_version（被重置者旧 token 立即失效，D3）。"""
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
