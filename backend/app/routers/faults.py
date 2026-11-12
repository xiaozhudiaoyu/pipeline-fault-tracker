# 路由模块：/api/faults —— 故障记录接口（本项目核心业务）。
#
# 第三阶段权限模型（需求三 + 四）：所有端点要求登录；动作类端点走独立的
# POST /{id}/{action}，路由层只做「取当前用户 → 转交 crud 校验并落库」，具体
# 权限判定（角色×归属×状态三维）在 auth.check_can_*、事务与时间线在 crud。
#
#   GET    /api/faults                故障查询（角色视图 + 筛选，分页，occurred_at 倒序）
#   GET    /api/faults/export         导出 CSV（复用列表口径，不分页，流式响应）
#   POST   /api/faults                故障登记（created_by 从当前用户取）
#   GET    /api/faults/{id}           单条详情（can_view 检查）
#   PATCH  /api/faults/{id}           修改故障信息（pending + 创建人或 admin）
#   GET    /api/faults/{id}/timelines 时间线（同 can_view）
#   POST   /api/faults/{id}/assign    指派（admin）
#   POST   /api/faults/{id}/reassign  改派（admin，理由必填）
#   POST   /api/faults/{id}/start     开始处理（当前负责人，pending→processing）
#   POST   /api/faults/{id}/progress  追加进展（当前负责人，processing 内）
#   POST   /api/faults/{id}/submit    提交结果（当前负责人，processing→awaiting_confirmation）
#   POST   /api/faults/{id}/confirm   确认完成（创建人 或 admin 代确认，→ done）
#   POST   /api/faults/{id}/return    退回处理（创建人，或创建人不可用时管理员代退回，awaiting→processing）
#   POST   /api/faults/{id}/priority  优先级调整（admin 或创建人，done 之前）
#
# D5 决策：旧 PATCH /{id}/transition 已移除，改由上述动作端点覆盖，避免"知道
# 目标状态就能绕过状态机"的后门。相关异常类 HandlingNoteRequiredError /
# HandlingNoteLockedError 在 exceptions 保留（其他脚本兼容），但代码路径不再触发。
#
# 命名注意：查询参数 status 与 fastapi.status 模块同名，故本文件【不】import fastapi.status，
# 需要 HTTP 状态码处直接用数字字面量（如 201），避免命名遮蔽。

import csv
import io
from datetime import datetime, timezone
from typing import Iterator

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..auth import CurrentUser
from ..database import get_db
from ..models import FaultPriority, FaultStatus

router = APIRouter(prefix="/api/faults", tags=["faults"])


@router.get("", response_model=schemas.FaultListOut)
def list_faults(
    user: CurrentUser,
    pipeline_id: int | None = Query(default=None, ge=1, description="按流水线 ID 筛选，不传=全部"),
    status: FaultStatus | None = Query(default=None, description="按处理状态筛选"),
    priority: FaultPriority | None = Query(default=None, description="按优先级筛选：normal/urgent"),
    assignee_id: int | None = Query(default=None, ge=1, description="按负责人 ID 筛选（需求四.4）"),
    unassigned: bool = Query(default=False, description="true 时只看未指派故障（管理员用）"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    size: int = Query(default=20, ge=1, le=100, description="每页条数，1~100"),
    db: Session = Depends(get_db),
) -> schemas.FaultListOut:
    """分页查询故障列表：默认按角色过滤（admin 全量、handler 自己或分派给自己、user 仅自己创建）。

    user: CurrentUser —— 依赖注入的当前登录用户，同时充当视图过滤器（crud._viewer_filter）。
    非 admin 传 assignee_id/unassigned 时，与角色视图 AND 叠加，得到"交集视图"（不越权）。
    """
    items, total = crud.list_faults(
        db,
        viewer=user,
        pipeline_id=pipeline_id,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        unassigned=unassigned,
        page=page,
        size=size,
    )
    return schemas.FaultListOut(
        items=[schemas.FaultOut.model_validate(f) for f in items],
        total=total,
        page=page,
        size=size,
    )


# 导出 CSV 表头（原 10 列 + 第二阶段 priority；第三阶段追加 creator/assignee 便于离线归属核对）
EXPORT_CSV_HEADER = [
    "id",
    "pipeline_code",
    "pipeline_name",
    "location",
    "occurred_at",
    "symptom",
    "status",
    "priority",
    "handling_note",
    "created_at",
    "closed_at",
    "creator",
    "assignee",
]


def _csv_datetime(value: datetime | None) -> str:
    """导出时间列格式：「YYYY-MM-DD HH:mm:ss」，与前端列表页展示格式一致（formatDateTime），
    Excel 可直接识别为日期时间；空值（如未结案的 closed_at）导空串。
    """
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _csv_user(user) -> str:
    """导出创建人/负责人列：显示 display_name，历史数据（None）导空串。"""
    if user is None:
        return ""
    return user.display_name


@router.get(
    "/export",
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV 文件流（UTF-8 带 BOM）"},
        422: {"model": schemas.ErrorOut, "description": "查询参数校验失败"},
    },
)
def export_faults(
    user: CurrentUser,
    pipeline_id: int | None = Query(default=None, ge=1, description="按流水线 ID 筛选，不传=全部"),
    status: FaultStatus | None = Query(default=None, description="按处理状态筛选"),
    priority: FaultPriority | None = Query(default=None, description="按优先级筛选：normal/urgent"),
    assignee_id: int | None = Query(default=None, ge=1, description="按负责人 ID 筛选"),
    unassigned: bool = Query(default=False, description="true 时只导出未指派故障"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出当前筛选下的全部故障（角色视图 + 传入的筛选参数）为 CSV。

    【路由顺序坑】本端点必须注册在 /{fault_id} 之前，否则 "export" 会被当作 fault_id 转整数 → 422。
    流式实现与 BOM/RFC4180 转义细节沿用旧版（见 git 历史），未变。
    """
    faults = crud.list_faults_for_export(
        db,
        viewer=user,
        pipeline_id=pipeline_id,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        unassigned=unassigned,
    )

    def _rows() -> Iterator[bytes]:
        yield "\ufeff".encode("utf-8")
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(EXPORT_CSV_HEADER)
        yield buf.getvalue().encode("utf-8")
        for f in faults:
            buf.seek(0)
            buf.truncate(0)
            writer.writerow(
                [
                    f.id,
                    f.pipeline.code,
                    f.pipeline.name,
                    f.location,
                    _csv_datetime(f.occurred_at),
                    f.symptom,
                    f.status.value,
                    f.priority.value,
                    f.handling_note if f.handling_note is not None else "",
                    _csv_datetime(f.created_at),
                    _csv_datetime(f.closed_at),
                    _csv_user(f.created_by),
                    _csv_user(f.assignee),
                ]
            )
            yield buf.getvalue().encode("utf-8")

    filename = f"faults_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.csv"
    return StreamingResponse(
        _rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/{fault_id}",
    response_model=schemas.FaultOut,
    responses={404: {"model": schemas.ErrorOut, "description": "故障记录不存在或无权查看"}},
)
def get_fault(
    fault_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> schemas.FaultOut:
    """按编号返回单条故障详情。无权限与不存在都返回 404（不泄露"这条存在但你看不到"）。"""
    return schemas.FaultOut.model_validate(crud.get_fault(db, fault_id, viewer=user))


@router.patch(
    "/{fault_id}",
    response_model=schemas.FaultOut,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非创建人且非管理员，或状态已过 pending"},
        404: {"model": schemas.ErrorOut, "description": "故障记录不存在或无权查看"},
        409: {"model": schemas.ErrorOut, "description": "已过 pending，需先退回才能修改"},
        422: {"model": schemas.ErrorOut, "description": "请求体未通过校验"},
    },
)
def update_fault(
    fault_id: int,
    payload: schemas.FaultUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """修改故障基础信息（location/symptom）。

    第三阶段权限模型：pending + (创建人 或 admin)。priority/handling_note 静默忽略
    （分别走 /priority 端点与 /submit 动作）。状态过了 pending 会 409，非归属人会 403。
    """
    return schemas.FaultOut.model_validate(
        crud.update_fault(db, fault_id, payload, viewer=user)
    )


@router.post(
    "",
    response_model=schemas.FaultOut,
    status_code=201,
    responses={
        404: {"model": schemas.ErrorOut, "description": "pipeline_id 指向的流水线不存在"},
        422: {"model": schemas.ErrorOut, "description": "请求体未通过校验"},
    },
)
def create_fault(
    payload: schemas.FaultCreate,
    response: Response,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """登记新故障：created_by_id 从当前登录用户取，同时写入 create 时间线（同事务）。

    · 不接受请求体指定 created_by_id（防伪造）；
    · status 强制 pending，priority 走 schema 默认；
    · 201 附带 Location 头指向新建资源。
    """
    fault = crud.create_fault(db, payload, creator=user)
    response.headers["Location"] = f"/api/faults/{fault.id}"
    return schemas.FaultOut.model_validate(fault)


# ── 处理闭环动作端点（第三阶段需求四）────────────────────────────────
# 每个动作一个子资源端点，请求体只承载必要参数（assignee_id/reason/note/priority）；
# 状态迁移与权限判定完全在 crud + auth，路由层不做二次判断（保持"薄"）。


@router.get(
    "/{fault_id}/timelines",
    response_model=list[schemas.TimelineOut],
    responses={404: {"model": schemas.ErrorOut, "description": "故障记录不存在或无权查看"}},
)
def list_timelines(
    fault_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> list[schemas.TimelineOut]:
    """按时间正序返回某条故障的完整时间线（含历史导入的 is_imported=True 记录）。"""
    entries = crud.list_timelines(db, fault_id, viewer=user)
    return [schemas.TimelineOut.model_validate(e) for e in entries]


@router.post(
    "/{fault_id}/assign",
    response_model=schemas.FaultOut,
    status_code=200,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非管理员，或接手人非启用 handler"},
        404: {"model": schemas.ErrorOut, "description": "故障不存在"},
        409: {"model": schemas.ErrorOut, "description": "当前状态或已有负责人，不允许指派"},
    },
)
def assign_fault(
    fault_id: int,
    payload: schemas.FaultAssignIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """指派：将未指派故障分配给指定 handler。仅管理员（check_can_assign）。"""
    fault = crud.assign_fault(db, fault_id, payload.assignee_id, actor=user)
    return schemas.FaultOut.model_validate(fault)


@router.post(
    "/{fault_id}/reassign",
    response_model=schemas.FaultOut,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非管理员，或接手人非法"},
        404: {"model": schemas.ErrorOut, "description": "故障不存在"},
        409: {"model": schemas.ErrorOut, "description": "当前状态不允许改派（D6：待确认需先退回）"},
    },
)
def reassign_fault(
    fault_id: int,
    payload: schemas.FaultReassignIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """改派：pending/processing 状态下换负责人，理由必填并写入时间线。"""
    fault = crud.reassign_fault(
        db, fault_id, payload.assignee_id, payload.reason, actor=user
    )
    return schemas.FaultOut.model_validate(fault)


@router.post(
    "/{fault_id}/start",
    response_model=schemas.FaultOut,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非当前负责人"},
        409: {"model": schemas.ErrorOut, "description": "当前状态不是 pending"},
    },
)
def start_fault(
    fault_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> schemas.FaultOut:
    """开始处理：当前负责人点按钮，pending → processing。"""
    fault = crud.start_fault(db, fault_id, actor=user)
    return schemas.FaultOut.model_validate(fault)


@router.post(
    "/{fault_id}/progress",
    response_model=schemas.FaultOut,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非当前负责人"},
        409: {"model": schemas.ErrorOut, "description": "当前状态不是 processing"},
    },
)
def add_progress(
    fault_id: int,
    payload: schemas.FaultProgressIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """追加进展：processing 期间多次记录中间过程，不改变状态。"""
    fault = crud.add_progress(db, fault_id, payload.note, actor=user)
    return schemas.FaultOut.model_validate(fault)


@router.post(
    "/{fault_id}/submit",
    response_model=schemas.FaultOut,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非当前负责人"},
        409: {"model": schemas.ErrorOut, "description": "当前状态不是 processing"},
    },
)
def submit_fault(
    fault_id: int,
    payload: schemas.FaultSubmitIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """提交处理结果：processing → awaiting_confirmation；handling_note 一并落库。"""
    fault = crud.submit_fault(db, fault_id, payload.result_note, actor=user)
    return schemas.FaultOut.model_validate(fault)


@router.post(
    "/{fault_id}/confirm",
    response_model=schemas.FaultOut,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非创建人/非代确认 admin，或负责人自行确认"},
        409: {"model": schemas.ErrorOut, "description": "当前状态不是 awaiting_confirmation"},
    },
)
def confirm_fault(
    fault_id: int,
    payload: schemas.FaultConfirmIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """确认完成：awaiting_confirmation → done。创建人本人免理由；admin 代确认必填 reason。"""
    fault = crud.confirm_fault(db, fault_id, payload.reason, actor=user)
    return schemas.FaultOut.model_validate(fault)


@router.post(
    "/{fault_id}/return",
    response_model=schemas.FaultOut,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非创建人，且非创建人不可用时的代退回管理员"},
        409: {"model": schemas.ErrorOut, "description": "当前状态不是 awaiting_confirmation"},
    },
)
def return_fault(
    fault_id: int,
    payload: schemas.FaultReturnIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """退回处理：创建人退回，awaiting_confirmation → processing，理由必填并写入时间线。

    创建人已停用或旧故障无对应账号时，管理员可代退回（需求二.5），同样必填原因、负责人不变。
    """
    fault = crud.return_fault(db, fault_id, payload.reason, actor=user)
    return schemas.FaultOut.model_validate(fault)


@router.post(
    "/{fault_id}/priority",
    response_model=schemas.FaultOut,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非 admin 且非创建人"},
        409: {"model": schemas.ErrorOut, "description": "已 done，不允许再调整优先级"},
    },
)
def change_priority(
    fault_id: int,
    payload: schemas.FaultPriorityIn,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """优先级调整（AU9）：done 之前 admin 或创建人可调；不影响状态；记入时间线。"""
    fault = crud.change_priority(db, fault_id, payload.priority, actor=user)
    return schemas.FaultOut.model_validate(fault)
