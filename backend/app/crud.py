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

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from . import schemas
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
    FaultNotFoundError,
    HandlingNoteLockedError,
    HandlingNoteRequiredError,
    InvalidTransitionError,
    PermissionDeniedError,
    PipelineCodeDuplicateError,
    PipelineNotFoundError,
    UserNotFoundError,
    UsernameDuplicateError,
)
from .models import (
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
) -> None:
    """向 session 挂载一条时间线，**不 commit**——同事务由调用方末尾统一提交。

    需求四.2「状态更新与时间线插入在同一个 db.commit() 内」由此保证：任一处报错，
    外层 rollback 会让两者一起回到事务起点。operator=None 仅用于历史数据导入。
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


def add_progress(db: Session, fault_id: int, note: str, *, actor: User) -> PipelineFault:
    """追加进展：processing + 当前负责人；状态不变，进展写入时间线。"""
    fault = get_fault(db, fault_id)
    check_can_progress(actor, fault)
    _write_timeline(
        db, fault, TimelineAction.progress, actor,
        from_status=fault.status.value, to_status=fault.status.value,
        note=note,
    )
    db.commit()
    return get_fault(db, fault_id)


def submit_fault(
    db: Session, fault_id: int, result_note: str, *, actor: User
) -> PipelineFault:
    """提交处理结果：processing + 当前负责人 → awaiting_confirmation；handling_note 一并写入。"""
    fault = get_fault(db, fault_id)
    check_can_submit(actor, fault)
    from_status = fault.status
    fault.status = FaultStatus.awaiting_confirmation
    fault.handling_note = result_note
    _write_timeline(
        db, fault, TimelineAction.submit, actor,
        from_status=from_status.value, to_status=FaultStatus.awaiting_confirmation.value,
        note=result_note,
    )
    db.commit()
    return get_fault(db, fault_id)


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
    fault.closed_at = datetime.now()
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
