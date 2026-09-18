# 路由模块：/api/pipelines —— 流水线主数据接口。
#
# 提供列表查询与创建：
#   GET  ""   —— 供前端"故障登记"选择流水线、"列表筛选"下拉使用。
#   POST ""   —— 新增流水线，编码重复返回 409。
#
# 路由层职责：只管"接收请求、返回响应"，数据读写交给 crud，错误由 exceptions 的 handler 统一处理。
# 显式用 model_validate 把 ORM 对象转成响应 schema：既让 Pyright 类型检查通过，
# 也明确表达"持久层对象 → 接口契约"的边界转换。

from fastapi import APIRouter, Depends, status
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


@router.post("", response_model=schemas.PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(body: schemas.PipelineCreate, db: Session = Depends(get_db)) -> schemas.PipelineOut:
    """创建流水线。

    编码（code）全表唯一，重复时返回 409 pipeline_code_duplicate。
    """
    pipeline = crud.create_pipeline(db, body)
    return schemas.PipelineOut.model_validate(pipeline)
