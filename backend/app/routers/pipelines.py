# 路由模块：/api/pipelines —— 流水线主数据接口。
#
# 第三阶段权限（D5 后调整）：
#   GET  ""   —— 登录即可，所有角色都需要看流水线列表（登记选线、筛选下拉）。
#   POST ""   —— **仅管理员**，主数据变更影响面大（错乱 code 会牵连故障归属）；
#                与需求"账号由管理员创建、不开放自助"的整体基调一致；页面归属留给 M6。
#
# 路由层职责：只管"接收请求、返回响应"，数据读写交给 crud，错误由 exceptions 的 handler 统一处理。
# 显式用 model_validate 把 ORM 对象转成响应 schema：既让 Pyright 类型检查通过，
# 也明确表达"持久层对象 → 接口契约"的边界转换。

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..auth import AdminUser, CurrentUser
from ..database import get_db

# 统一前缀 /api/pipelines；tags 与 main.py 的 openapi_tags 中 name 一字不差，Swagger 才会显示分组说明。
router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


@router.get("", response_model=list[schemas.PipelineOut])
def list_pipelines(
    user: CurrentUser, db: Session = Depends(get_db)
) -> list[schemas.PipelineOut]:
    """返回全部流水线，按 code 升序。登录即可（未登录 401，见 auth.get_current_user）。

    db: Session = Depends(get_db) —— 框架注入：每个请求发放一个 Session，请求结束自动关闭。
    user: CurrentUser —— 仅用作"必须登录"的门槛，具体角色不再过滤（主数据全系统共享）。
    """
    return [schemas.PipelineOut.model_validate(p) for p in crud.list_pipelines(db)]


@router.post("", response_model=schemas.PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    body: schemas.PipelineCreate,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> schemas.PipelineOut:
    """创建流水线（**仅管理员**，非 admin 403）。

    编码（code）全表唯一，重复时返回 409 pipeline_code_duplicate。
    """
    pipeline = crud.create_pipeline(db, body)
    return schemas.PipelineOut.model_validate(pipeline)
