# 路由模块：/api/pipelines —— 流水线主数据接口。
#
# 仅提供列表查询：供前端"故障登记"选择流水线、"列表筛选"下拉使用。
# 流水线主数据由 seed.py 初始化，本项目不提供前端管理界面（需求未要求，遵循最小范围）。
#
# 路由层职责：只管"接收请求、返回响应"，数据读写交给 crud，错误由 exceptions 的 handler 统一处理。
# 显式用 model_validate 把 ORM 对象转成响应 schema：既让 Pyright 类型检查通过，
# 也明确表达"持久层对象 → 接口契约"的边界转换。

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

# 统一前缀 /api/pipelines；tags 与 main.py 的 openapi_tags 中 name 一字不差，Swagger 才会显示分组说明。
router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


@router.get("", response_model=list[schemas.PipelineOut])
def list_pipelines(db: Session = Depends(get_db)) -> list[schemas.PipelineOut]:
    """返回全部流水线，按 code 升序。

    db: Session = Depends(get_db) —— 框架注入：每个请求发放一个 Session，请求结束自动关闭。
    这是 FastAPI 依赖注入管理数据库会话的标准模式（见 database.py 的 get_db）。
    """
    return [schemas.PipelineOut.model_validate(p) for p in crud.list_pipelines(db)]
