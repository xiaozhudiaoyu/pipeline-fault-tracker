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
#   · extra="forbid" —— 客户端多传拼错名字的字段直接 422，不被静默丢弃；
#   · field_validator —— 跨值/带容差的校验（如时间不晚于当前）用装饰器，同样汇入 422 details。

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import FaultPriority, FaultRole, FaultStatus, TimelineAction


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
class UserBrief(BaseModel):
    """故障响应里嵌套的用户卡：仅 id/username/display_name/role。

    与 UserOut 分开是因为：列表/详情接口需显示创建人与负责人，但不能暴
    露 is_active/token_version/created_at 等账户字段（需求三.3 “列表不展示登录无关信息”）。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: FaultRole


class FaultCreate(BaseModel):
    """POST /api/faults 的请求体：登记一条新故障。

    校验规则直接写在字段上，非法输入 FastAPI 自动返回 422，业务代码不用写 if。
    注意：status / handling_note / closed_at 不在这里 —— 新故障一律由后端置为 pending，
    不允许客户端在登记时直接指定状态（防止绕过状态流转校验）。
    """

    model_config = ConfigDict(extra="forbid")

    pipeline_id: int = Field(ge=1, description="所属流水线 ID，必须已存在")
    location: str = Field(
        min_length=2,
        max_length=200,
        pattern=r"^\S.*$",
        description="故障发生位置，如 3号工位传送带；首字符不得为空白",
    )
    occurred_at: datetime = Field(description="故障发生时间（业务时间，ISO 8601 格式），不得晚于当前时间")
    symptom: str = Field(min_length=5, max_length=1000, description="故障现象描述，5~1000 字")
    # 优先级可选，缺省即普通（需求二.1）；非法取值（如 "high"）由枚举校验直接 422，
    # 与 status 不同：登记时允许选优先级，但不允许选状态（防绕过流转校验的既有规则不变）。
    priority: FaultPriority = Field(default=FaultPriority.normal, description="优先级：normal/urgent，默认普通")

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_not_in_future(cls, v: datetime) -> datetime:
        """业务时间不能是未来 —— 登记的是"已发生"的故障。

        容忍 60 秒时钟偏移：客户端与服务器时钟未必同步，秒级误差不应误拦。
        aware/naive 统一换算成 aware 再比，避免 Python 直接比较抛 TypeError（会变成 500）。
        """
        now = datetime.now(timezone.utc)
        v_aware = v if v.tzinfo is not None else v.astimezone()
        if v_aware > now + timedelta(seconds=60):
            raise ValueError("故障发生时间不得晚于当前时间")
        return v


class FaultOut(BaseModel):
    """故障响应体：列表与详情共用。

    pipeline 字段是嵌套的 PipelineOut —— 前端列表要直接显示流水线名称，
    嵌套结构省去前端二次请求。为避免 N+1 查询，crud 层查询时用 selectinload 预加载 pipeline。

    第三阶段新增（需求四.1）：created_by / assignee 嵌套 UserBrief，列表与详情展示
    负责人与创建人。旧数据（created_by_id/assignee_id 为 NULL）返回 null，前端渲染
    “历史数据”文案（需求一）；服务端不直接返回字符串。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    pipeline: PipelineOut
    location: str
    occurred_at: datetime
    symptom: str
    status: FaultStatus
    priority: FaultPriority
    handling_note: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    # 第三阶段新增
    created_by: UserBrief | None = None
    assignee: UserBrief | None = None


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
        description="处理说明；目标为 done 时必填（crud 层校验）；一旦提供不得少于 5 字",
    )

    @field_validator("handling_note")
    @classmethod
    def handling_note_min_length(cls, v: str | None) -> str | None:
        """业务规则：处理说明一旦提供就必须有实质内容（strip 后 ≥5 字）。

        None 放行（语义是"本次不改说明"）；前端已把空串转成 null，
        直接调 API 传 "  ok  " 这类敷衍内容会被这里拦下（422）。
        """
        if v is not None and len(v.strip()) < 5:
            raise ValueError("处理说明一旦提供，去除首尾空格后不得少于 5 字")
        return v


class FaultUpdate(BaseModel):
    """PATCH /api/faults/{id} 的请求体：修改故障基础信息（不含状态流转）。

    全部字段可选，只改"传了的"（crud 层用 model_dump(exclude_unset=True) 区分
    "没传"与"传了 null"）。状态流转仍走 /transition 端点，两处规则不重叠。
    业务规则：done 后 handling_note 锁定不可再改（crud 层校验 → 409）。
    """

    model_config = ConfigDict(extra="forbid")

    location: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
        pattern=r"^\S.*$",
        description="故障发生位置；首字符不得为空白",
    )
    symptom: str | None = Field(default=None, min_length=5, max_length=1000, description="故障现象描述，5~1000 字")
    # 修改优先级与状态流转是两个端点：这里改 priority 不会碰 status（crud 只应用传了的字段）。
    priority: FaultPriority | None = Field(
        default=None,
        description="优先级：normal/urgent；不传即不改，非法取值 422",
    )
    handling_note: str | None = Field(
        default=None,
        min_length=5,
        max_length=2000,
        description="处理说明，不少于 5 字；不接受显式 null（不支持清空）；done 后不可再改（crud 层校验）",
    )

    @field_validator("handling_note")
    @classmethod
    def handling_note_not_null(cls, v: str | None) -> str | None:
        """修改场景不支持"传 null 清空说明"：要么不传（不改），要么传 ≥5 字的有效内容。
        同时拦住"5 个空格+1 个字"这类绕过字段级 min_length 的写法（strip 后验长度）。"""
        if v is None:
            raise ValueError("handling_note 不支持显式置空，不传即不修改")
        if len(v.strip()) < 5:
            raise ValueError("处理说明一旦提供，去除首尾空格后不得少于 5 字")
        return v


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


# ── 用户与认证（第三阶段）───────────────────────────────────────────
class LoginRequest(BaseModel):
    """POST /api/auth/login 请求体。"""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=50, description="登录用户名")
    password: str = Field(min_length=1, max_length=200, description="明文密码，服务端 bcrypt 比对")


class TokenResponse(BaseModel):
    """登录成功后的 JWT 响应。"""

    access_token: str = Field(description="JWT，前端存内存/localStorage，后续接口放 Authorization: Bearer")
    token_type: str = Field(default="bearer", description="OAuth 2 规定的类型，固定 bearer")
    expires_in: int = Field(description="有效期（秒），前端可据此提前刷新")


class UserOut(BaseModel):
    """用户响应体（不返回 password_hash、token_version）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: FaultRole
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    """管理员创建用户请求体（seed 脚本与 M4 用户管理接口共用）。"""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50, description="登录名，全表唯一")
    password: str = Field(min_length=6, max_length=200, description="初始明文密码，存 bcrypt 哈希")
    display_name: str = Field(min_length=1, max_length=100, description="展示名称")
    role: FaultRole = Field(description="固定三角色之一")


# ── 故障处理闭环动作请求体（第三阶段需求四）─────────────────────────
# 每个动作一个子资源端点（需求四.3、D5），不接受客户端直接传目标状态；状态入库
# 完全由服务端基于当前状态 + 角色判定。extra=forbid 防少字段名递延到 crud。
class FaultAssignIn(BaseModel):
    """POST /api/faults/{id}/assign：管理员将未指派故障指派给处理人员。"""

    model_config = ConfigDict(extra="forbid")

    assignee_id: int = Field(ge=1, description="接手人用户 ID（必须为 handler 且启用）")


class FaultReassignIn(BaseModel):
    """POST /api/faults/{id}/reassign：改派，理由必填（需求四.3）。"""

    model_config = ConfigDict(extra="forbid")

    assignee_id: int = Field(ge=1, description="新负责人用户 ID")
    reason: str = Field(min_length=2, max_length=500, description="改派理由，时间线写入、不可篡改")

    @field_validator("reason")
    @classmethod
    def _reason_strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("改派理由去除首尾空格后不得少于 2 字")
        return v


class FaultProgressIn(BaseModel):
    """POST /api/faults/{id}/progress：处理中追加进展（不改变状态）。"""

    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=2, max_length=2000, description="进展内容，strip 后 ≥ 2 字")

    @field_validator("note")
    @classmethod
    def _note_strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("进展内容去除首尾空格后不得少于 2 字")
        return v


class FaultSubmitIn(BaseModel):
    """POST /api/faults/{id}/submit：处理人员提交结果，pending→awaiting_confirmation。"""

    model_config = ConfigDict(extra="forbid")

    result_note: str = Field(min_length=5, max_length=2000, description="处理结果说明，写入 fault.handling_note 与时间线")

    @field_validator("result_note")
    @classmethod
    def _note_strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("处理结果说明去除首尾空格后不得少于 5 字")
        return v


class FaultConfirmIn(BaseModel):
    """POST /api/faults/{id}/confirm：创建人确认完成（或 admin 代确认，理由必填）。"""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="确认备注；admin 代确认时必填（需求 SM11）",
    )


class FaultReturnIn(BaseModel):
    """POST /api/faults/{id}/return：创建人退回至 processing（需求四.3、SM9）。"""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=2, max_length=500, description="退回理由，必填")

    @field_validator("reason")
    @classmethod
    def _reason_strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("退回理由去除首尾空格后不得少于 2 字")
        return v


class FaultPriorityIn(BaseModel):
    """POST /api/faults/{id}/priority：调整优先级，不影响状态（需求二.2）。"""

    model_config = ConfigDict(extra="forbid")

    priority: FaultPriority = Field(description="目标优先级：normal/urgent")


class TimelineOut(BaseModel):
    """GET /api/faults/{id}/timelines 的响应项：时间线一条记录。

    operator_name 优先取当前用户 display_name，用户已删时回退快照；历史导入记录
    is_imported=True，前端展示“历史数据”。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    fault_id: int
    action: TimelineAction
    operator_id: int | None
    operator_name: str | None = None
    from_status: str | None
    to_status: str | None
    from_assignee_id: int | None
    to_assignee_id: int | None
    note: str | None
    is_imported: bool
    created_at: datetime
