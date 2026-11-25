# 路由模块：/api/items —— 示例实体接口（标准 CRUD 五件套）。
#
#   GET    /api/items          列表查询（按状态筛选，分页，created_at 倒序）
#   POST   /api/items          创建（201 + Location 头）
#   GET    /api/items/{id}     单条详情
#   PATCH  /api/items/{id}     部分更新
#   DELETE /api/items/{id}     删除（204）
#
# 路由层只管"收发请求"，业务规则（唯一性校验）在 crud 层，错误结构由 exceptions 统一。
#
# 命名注意：查询参数 status 与 fastapi.status 模块同名，故本文件【不】import fastapi.status，
# 需要 HTTP 状态码处直接用数字字面量（如 201、204），避免命名遮蔽。

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..models import ItemStatus

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=schemas.ItemListOut)
def list_items(
    status: ItemStatus | None = Query(default=None, description="按状态筛选：active/archived，不传=全部"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    size: int = Query(default=20, ge=1, le=100, description="每页条数，1~100，防止一次拉取过多"),
    db: Session = Depends(get_db),
) -> schemas.ItemListOut:
    """分页查询列表，默认按 created_at 倒序。

    参数取值规则（FastAPI 核心）：这些参数都不在路径里、且是标量/枚举类型，
    故全部按【查询参数】取值，即 /api/items?status=active&page=1&size=20。
      · status: ItemStatus | None —— FastAPI 自动把字符串 "active" 转成 ItemStatus.active 枚举，
        非法值（如 ?status=xxx）直接 422，业务代码拿到的一定是合法枚举或 None；
      · Query(ge=1, le=100) —— 查询参数也能带校验约束，越界直接 422。

    返回包一层 ItemListOut（items+total+page+size）：前端分页组件需要 total 算总页数。
    """
    items, total = crud.list_items(db, status=status, page=page, size=size)
    return schemas.ItemListOut(
        items=[schemas.ItemOut.model_validate(f) for f in items],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{item_id}",
    response_model=schemas.ItemOut,
    responses={404: {"model": schemas.ErrorOut, "description": "记录不存在"}},
)
def get_item(item_id: int, db: Session = Depends(get_db)) -> schemas.ItemOut:
    """按编号返回单条详情，演示【路径参数】：/api/items/2。

    item_id: int —— 名字在路径 {item_id} 里，故按路径参数取值；
    URL 里的 "2" 自动转整数；转不了（如 /api/items/abc）直接 422。
    找不到记录时 crud 抛 ItemNotFoundError，由 handler 转成 404 统一错误结构。
    """
    return schemas.ItemOut.model_validate(crud.get_item(db, item_id))


@router.post(
    "",
    response_model=schemas.ItemOut,
    status_code=201,
    responses={
        409: {"model": schemas.ErrorOut, "description": "名称已存在"},
        422: {"model": schemas.ErrorOut, "description": "请求体未通过校验"},
    },
)
def create_item(
    payload: schemas.ItemCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.ItemOut:
    """创建记录，演示【请求体】：客户端 POST 一段 JSON，FastAPI 用 ItemCreate 校验后交给 payload。

    语法要点：
      · payload: ItemCreate —— 参数类型是 Pydantic 模型 → 从"请求体 body"取值；
        校验由 ItemCreate 的 Field 规则完成，非法直接 422；
      · status_code=201 —— "创建成功"的标准状态码（默认 200）；
      · response: Response —— 框架注入的响应对象，用它回写 Location 头（201 的规范动作，
        告诉客户端新资源在哪）；它不是接口参数，Swagger 不会多出表单字段。
    """
    item = crud.create_item(db, payload)
    response.headers["Location"] = f"/api/items/{item.id}"
    return schemas.ItemOut.model_validate(item)


@router.patch(
    "/{item_id}",
    response_model=schemas.ItemOut,
    responses={
        404: {"model": schemas.ErrorOut, "description": "记录不存在"},
        409: {"model": schemas.ErrorOut, "description": "名称与现有记录冲突"},
        422: {"model": schemas.ErrorOut, "description": "请求体未通过校验"},
    },
)
def update_item(
    item_id: int,
    payload: schemas.ItemUpdate,
    db: Session = Depends(get_db),
) -> schemas.ItemOut:
    """部分更新。PATCH 语义是"部分更新"：ItemUpdate 字段全部可选，
    crud 层用 exclude_unset 只应用客户端传了的字段。
    """
    return schemas.ItemOut.model_validate(crud.update_item(db, item_id, payload))


@router.delete(
    "/{item_id}",
    status_code=204,
    responses={404: {"model": schemas.ErrorOut, "description": "记录不存在"}},
)
def delete_item(item_id: int, db: Session = Depends(get_db)) -> Response:
    """删除记录。成功返回 204 无内容（标准删除语义），不存在则 404。"""
    crud.delete_item(db, item_id)
    return Response(status_code=204)
