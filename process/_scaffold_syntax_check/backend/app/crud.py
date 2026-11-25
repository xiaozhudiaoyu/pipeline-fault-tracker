# 模块：CRUD 数据访问层 —— 所有数据库读写与业务规则校验集中在此。
#
# 分层职责：
#   routers/  —— 只管"接收请求、返回响应"，不写 SQL、不写业务判断；
#   crud.py   —— 管"怎么读写数据库 + 业务规则校验"，不碰 HTTP（异常由 exceptions.py 定义）；
#   models.py —— 管"表结构"。
#
# 为什么业务规则（唯一性校验等）放 crud 而不是 router？
#   规则应跟着数据层走，不能只在 HTTP 层校验。放 crud 保证"无论从哪进来（HTTP/脚本/任务），
#   规则都生效"。
#
# SQLAlchemy 2 查询风格：select() 构造语句，db.scalars()/db.scalar() 执行。
# 所有 db: Session 由路由层 Depends(get_db) 注入，本层不负责开关 session。

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas
from .exceptions import ItemNameDuplicateError, ItemNotFoundError
from .models import Item, ItemStatus


def list_items(
    db: Session,
    *,
    status: ItemStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Item], int]:
    """分页查询列表，返回 (当前页记录, 总数)。

    筛选条件可选（None 表示不限制）；默认按 created_at 倒序（最新在前）。
    total 用独立的 count 查询：分页查询只取当前页，无法得知总数，必须单独 COUNT。
    两个查询共用同一套 where 条件，保证 total 与 items 的筛选口径一致。
    """
    stmt = select(Item)
    count_stmt = select(func.count()).select_from(Item)

    if status is not None:
        stmt = stmt.where(Item.status == status)
        count_stmt = count_stmt.where(Item.status == status)

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(Item.created_at.desc()).offset((page - 1) * size).limit(size)
    items = list(db.scalars(stmt))
    return items, total


def get_item(db: Session, item_id: int) -> Item:
    """按 ID 取记录，不存在则抛 ItemNotFoundError（404）。"""
    item = db.get(Item, item_id)
    if item is None:
        raise ItemNotFoundError(item_id)
    return item


def create_item(db: Session, data: schemas.ItemCreate) -> Item:
    """新增记录。业务规则：name 全表唯一，重复则抛 ItemNameDuplicateError（409）。"""
    # 先查唯一性，给出明确的业务错误（而非数据库层 IntegrityError 500）
    existing = db.scalar(select(Item).where(Item.name == data.name))
    if existing is not None:
        raise ItemNameDuplicateError(data.name)

    item = Item(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)  # refresh 拿到数据库生成的 id / created_at
    return item


def update_item(db: Session, item_id: int, data: schemas.ItemUpdate) -> Item:
    """部分更新：只应用客户端"传了的"字段。

    exclude_unset=True：没传的字段不动。
    name 改动时同样查重（排除自身），演示唯一性规则在更新路径同样生效。
    """
    item = get_item(db, item_id)
    changes = data.model_dump(exclude_unset=True)

    new_name = changes.get("name")
    if new_name is not None and new_name != item.name:
        existing = db.scalar(select(Item).where(Item.name == new_name))
        if existing is not None:
            raise ItemNameDuplicateError(new_name)

    for field, value in changes.items():
        setattr(item, field, value)
    db.commit()
    # commit 触发 updated_at onupdate；重新查询拿数据库落盘后的完整对象
    return get_item(db, item_id)


def delete_item(db: Session, item_id: int) -> None:
    """按 ID 删除记录。先查（不存在抛 404）再删，避免对空操作静默成功。"""
    item = get_item(db, item_id)
    db.delete(item)
    db.commit()
