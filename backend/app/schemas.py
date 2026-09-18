# 模块：Pydantic 数据模型层 —— 定义接口"收什么、发什么"的结构与校验规则。
#
# 与 models.py（SQLAlchemy ORM）的职责区分（同 python_learn 的分层理念）：
#   Pydantic BaseModel —— 活在接口边界，做请求校验与响应序列化；
#   SQLAlchemy Base    —— 活在持久层，做表映射与 SQL 生成。
#   两者字段名相似但职责不同，不能互相顶替。
#
# Pydantic 2 关键写法：
#   · model_config = ConfigDict(from_attributes=True) —— 允许从 ORM 对象属性读取（替代 v1 的 orm_mode）；
#   · Field(...) 上的约束（min_length/ge 等）由 FastAPI 在运行时自动校验，非法输入直接 422；
#   · extra="forbid" —— 客户端多传拼错名字的字段直接 422，不被静默丢弃。

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import FaultStatus


# ── 流水线（主数据）──────────────────────────────────────────────────────
class PipelineOut(BaseModel):
    """流水线响应体。from_attributes=True 让 FastAPI 能直接把 ORM 的 Pipeline 对象序列化成它。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None = None


class PipelineCreate(BaseModel):
    """新增流水线请求体（供 seed 脚本或后续管理功能使用）。"""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=50, description="流水线编码，全表唯一，如 LINE-A")
    name: str = Field(min_length=1, max_length=100, description="流水线名称")
    description: str | None = Field(default=None, description="描述，选填")


# ── 故障记录（核心业务实体）──────────────────────────────────────────────
class FaultCreate(BaseModel):
    """POST /api/faults 的请求体：登记一条新故障。

    校验规则直接写在字段上，非法输入 FastAPI 自动返回 422，业务代码不用写 if。
    注意：status / handling_note / closed_at 不在这里 —— 新故障一律由后端置为 pending，
    不允许客户端在登记时直接指定状态（防止绕过状态流转校验）。
    """

    model_config = ConfigDict(extra="forbid")

    pipeline_id: int = Field(ge=1, description="所属流水线 ID，必须已存在")
    location: str = Field(min_length=2, max_length=200, description="故障发生位置，如 3号工位传送带")
    occurred_at: datetime = Field(description="故障发生时间（业务时间，ISO 8601 格式）")
    symptom: str = Field(min_length=5, description="故障现象描述，至少 5 字")


class FaultOut(BaseModel):
    """故障响应体：列表与详情共用。

    pipeline 字段是嵌套的 PipelineOut —— 前端列表要直接显示流水线名称，
    嵌套结构省去前端二次请求。为避免 N+1 查询，crud 层查询时用 selectinload 预加载 pipeline。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    pipeline: PipelineOut
    location: str
    occurred_at: datetime
    symptom: str
    status: FaultStatus
    handling_note: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class FaultTransition(BaseModel):
    """PATCH /api/faults/{id}/transition 的请求体：推进故障状态。

    target_status 用 FaultStatus 枚举，Pydantic 会自动校验取值只能是 pending/processing/done，
    非法值直接 422。状态流转的【业务规则】（如 done 不可逆、done 必填 note）在 crud 层校验，
    这里只管"结构合法"。
    """

    model_config = ConfigDict(extra="forbid")

    target_status: FaultStatus = Field(description="目标状态：pending/processing/done")
    handling_note: str | None = Field(
        default=None,
        max_length=2000,
        description="处理说明；目标为 done 时必填（crud 层校验）",
    )


class FaultListOut(BaseModel):
    """分页列表响应体。

    为什么包一层而不直接返回数组？
      前端分页组件需要 total 才能算总页数；直接返回数组会丢失总数信息。
      items + total + page + size 是分页接口的标准四件套。
    """

    items: list[FaultOut]
    total: int = Field(description="符合筛选条件的总记录数（非当前页条数）")
    page: int = Field(description="当前页码，从 1 开始")
    size: int = Field(description="每页条数")


# ── 统一错误响应结构（同 python_learn/todo_api 风格）──────────────────────
class FieldErrorOut(BaseModel):
    """字段级校验明细，只在校验类错误（422 / 400）里出现。"""

    field: str = Field(description="出问题的字段路径，如 body.symptom、query.page")
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
