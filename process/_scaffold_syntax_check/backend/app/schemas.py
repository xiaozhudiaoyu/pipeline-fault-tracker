# 模块：Pydantic 数据模型层 —— 定义接口"收什么、发什么"的结构与校验规则。
#
# 与 models.py（SQLAlchemy ORM）的职责区分：
#   Pydantic BaseModel —— 活在接口边界，做请求校验与响应序列化；
#   SQLAlchemy Base    —— 活在持久层，做表映射与 SQL 生成。
#   两者字段名相似但职责不同，不能互相顶替。
#
# Pydantic 2 关键写法：
#   · model_config = ConfigDict(from_attributes=True) —— 允许从 ORM 对象属性读取（替代 v1 的 orm_mode）；
#   · Field(...) 上的约束（min_length/ge 等）由 FastAPI 在运行时自动校验，非法输入直接 422；
#   · extra="forbid" —— 客户端多传拼错名字的字段直接 422，不被静默丢弃；
#   · field_validator —— 跨值/带容差的校验用装饰器，同样汇入 422 details。

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ItemStatus


# ── 示例实体 Item ───────────────────────────────────────────────────────
class ItemCreate(BaseModel):
    """POST /api/items 的请求体：创建一条记录。

    校验规则直接写在字段上，非法输入 FastAPI 自动返回 422，业务代码不用写 if。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100, description="名称，全表唯一")
    description: str | None = Field(default=None, max_length=2000, description="描述，选填")


class ItemUpdate(BaseModel):
    """PATCH /api/items/{id} 的请求体：部分更新。

    全部字段可选，只改"传了的"（crud 层用 model_dump(exclude_unset=True) 区分
    "没传"与"传了 null"）。description 不接受显式 null（不支持清空，不传即不改）。
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100, description="名称，全表唯一")
    description: str | None = Field(default=None, max_length=2000, description="描述；不接受显式 null")
    status: ItemStatus | None = Field(default=None, description="状态：active/archived")

    @field_validator("description")
    @classmethod
    def description_not_null(cls, v: str | None) -> str | None:
        """修改场景不支持"传 null 清空描述"：要么不传（不改），要么传有效内容。"""
        if v is None:
            raise ValueError("description 不支持显式置空，不传即不修改")
        return v


class ItemOut(BaseModel):
    """响应体：列表与详情共用。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    status: ItemStatus
    created_at: datetime
    updated_at: datetime


class ItemListOut(BaseModel):
    """分页列表响应体。

    为什么包一层而不直接返回数组？
      前端分页组件需要 total 才能算总页数；直接返回数组会丢失总数信息。
      items + total + page + size 是分页接口的标准四件套。
    """

    items: list[ItemOut]
    total: int = Field(description="符合筛选条件的总记录数（非当前页条数）")
    page: int = Field(description="当前页码，从 1 开始")
    size: int = Field(description="每页条数")


# ── 统一错误响应结构 ────────────────────────────────────────────────────
class FieldErrorOut(BaseModel):
    """字段级校验明细，只在校验类错误（422 / 400）里出现。"""

    field: str = Field(description="出问题的字段路径，如 body.name、query.page")
    type: str = Field(description="机器可读的错误类型，如 missing、string_too_short")
    message: str = Field(description="人话说明")


class ErrorOut(BaseModel):
    """统一错误响应结构：所有非 2xx 的 JSON body 都长这个样。

    前端只写一段处理逻辑就能应对全部错误：按 code 分支、按 message 兜底展示、
    按 details 把错误标到对应输入框。路由上写 responses={404: {"model": ErrorOut}}
    就能在 Swagger 里看到它。
    """

    code: str = Field(description="稳定的错误码，给程序判断用，别拿它当文案")
    message: str = Field(description="给人看的说明，可能随时改，不要用它做逻辑判断")
    details: list[FieldErrorOut] = Field(default_factory=list, description="字段级明细；没有则为空列表")
