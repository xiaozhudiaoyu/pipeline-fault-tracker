# Pydantic v2 完整用法速查

> 基于 Pydantic 2.13.5，从入门到能干活。v1 老写法（`@validator`、`.dict()`、`class Config`）作为对比会标出来，遇到旧教程直接跳过。
>
> 本文档由 Qoder 会话整理落盘，作为项目内 Pydantic 用法的通用参考。

---

## 一、Pydantic 解决什么问题

Python 是动态类型语言，类型注解默认只是"给人看的文档"。Pydantic 让类型注解**在运行时真正生效**：

- 数据校验（构造对象时检查类型、范围、格式）
- 数据转换（`"123"` → `123`、`"2024-01-01"` → `datetime`）
- 序列化 / 反序列化（对象 ↔ 字典 ↔ JSON）
- 生成 JSON Schema（FastAPI 的 OpenAPI 文档就靠这个）

**核心心智模型**：类型注解 + 元数据（`Field(...)`）= 运行时校验规则。

---

## 二、安装与生态

```bash
pip install pydantic               # 核心
pip install pydantic[email]        # 带 EmailStr 等类型（依赖 email-validator）
pip install pydantic-settings      # 配置管理（从环境变量/.env 读）
pip install pydantic-extra-types   # 额外类型（颜色、坐标、货币等）
pip install pydantic-graph         # 状态机/工作流（较新）
```

**依赖关系**：

- `pydantic-core` —— Rust 实现的核心（自动装，性能关键）
- `annotated-types` —— `Annotated` 元数据标准（自动装）
- `typing-extensions` —— 类型兼容层（自动装）

---

## 三、BaseModel 基础

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    name: str = Field(min_length=1, max_length=50)
    email: str | None = None
    age: int = Field(default=0, ge=0, le=150)
    tags: list[str] = []

# 创建
u = User(id=1, name="alice")            # OK
u = User(id=1, name="alice", age="25")  # OK，"25" 自动转成 25
u = User(id=1, name="")                 # ValidationError: name 不能为空
u = User(id="x", name="alice")          # ValidationError: id 必须是 int

# 访问属性
print(u.id, u.name)

# 修改属性（默认不校验，除非 validate_assignment=True）
u.name = ""          # 不会报错（默认）
```

**v1 vs v2 对照**：

| v1 | v2 |
|---|---|
| `u.dict()` | `u.model_dump()` |
| `u.json()` | `u.model_dump_json()` |
| `User.parse_obj(d)` | `User.model_validate(d)` |
| `User.parse_raw(s)` | `User.model_validate_json(s)` |
| `@validator("x")` | `@field_validator("x")` |
| `@root_validator` | `@model_validator(mode="before"/"after")` |
| `class Config:` | `model_config = ConfigDict(...)` |
| `Field(regex=...)` | `Field(pattern=...)` |
| `Field(const=True)` | `Literal["x"]` |
| `.copy(update={...})` | `.model_copy(update={...})` |
| `.schema()` | `.model_json_schema()` |

---

## 四、Field 完整参数

```python
from pydantic import Field

Field(
    # ── 默认值 ────────────────────────────────
    default=None,                    # 静态默认值
    default_factory=list,            # 动态默认值（每次创建都调一次）

    # ── 别名（字段名和外部数据名不同时）──────
    alias="userId",                  # 输入时的别名（model_validate 用）
    alias_priority=2,                # 别名优先级
    validation_alias="user_id",      # 只用于校验（输入）
    serialization_alias="userId",    # 只用于序列化（输出）
    populate_by_name=True,           # 允许用字段名或别名（v2 新）

    # ── 通用约束 ──────────────────────────────
    title="User ID",                 # JSON Schema 标题
    description="用户唯一标识",       # JSON Schema 描述
    examples=[1, 2, 3],              # 示例值
    deprecated=True,                 # 标记为已废弃
    exclude=True,                    # 序列化时排除

    # ── 数字约束 ──────────────────────────────
    gt=0,                            # > 0
    ge=0,                            # >= 0
    lt=100,                          # < 100
    le=100,                          # <= 100
    multiple_of=5,                   # 必须是 5 的倍数
    allow_inf_nan=False,             # 不允许 inf/nan

    # ── 字符串约束 ────────────────────────────
    min_length=1,
    max_length=100,
    pattern=r"^\d{3}-\d{4}$",        # 正则（v1 是 regex）
    strip_whitespace=True,           # 自动去首尾空格
    to_lower=True,                   # 自动转小写
    to_upper=True,                   # 自动转大写

    # ── 集合约束 ──────────────────────────────
    min_length=1,                    # 列表/元组/集合的最小长度
    max_length=10,                   # 最大长度

    # ── Decimal 约束 ─────────────────────────
    max_digits=10,                   # 总位数
    decimal_places=2,                # 小数位数

    # ── 冻结 / 只读 ──────────────────────────
    frozen=True,                     # 不可修改（赋值会报错）
    validate_default=True,           # 默认值也要校验
)
```

**`default` vs `default_factory`**：

```python
class Bad(BaseModel):
    tags: list[str] = []          # 错！所有实例共享同一个 list

class Good(BaseModel):
    tags: list[str] = Field(default_factory=list)   # 对！每次创建新 list
```

---

## 五、类型系统

### 5.1 内置类型

```python
from typing import Optional, Union, Literal
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from pathlib import Path

class Model(BaseModel):
    # 基础类型
    a: int
    b: float
    c: str
    d: bool
    e: bytes

    # 可空
    f: Optional[int] = None          # 等价于 int | None
    g: int | None = None             # Python 3.10+ 推荐写法

    # 联合类型
    h: Union[int, str]               # 可以是 int 或 str
    i: int | str                     # 同上

    # 字面量
    j: Literal["asc", "desc"]        # 只能是这两个值之一

    # 日期时间（自动从字符串解析）
    k: datetime                      # "2024-01-01T10:00:00" → datetime
    l: date                          # "2024-01-01" → date
    m: time                          # "10:30:00" → time
    n: timedelta                     # "P1DT2H" → timedelta（ISO 8601）

    # 精确小数（金额必用）
    o: Decimal                       # "10.50" → Decimal("10.50")

    # UUID
    p: UUID                          # "550e8400-..." → UUID

    # 路径
    q: Path                          # 字符串 → Path 对象

    # 集合
    r: list[int]
    s: tuple[int, str]               # 固定长度元组
    t: tuple[int, ...]               # 可变长度元组
    u: set[str]
    v: dict[str, int]
    w: frozenset[str]

    # 任意类型
    x: Any                           # 不校验
    y: None                          # 只能是 None
```

### 5.2 Pydantic 特殊类型

```python
from pydantic import (
    EmailStr,            # 邮箱格式（需要 pip install pydantic[email]）
    AnyUrl, AnyHttpUrl, HttpUrl,   # URL 格式
    FileUrl,             # file:// URL
    PostgresDsn, MySQLDsn, RedisDsn, MongoDsn,  # 特定数据库 DSN
    SecretStr, SecretBytes,        # 密码字段（repr 时打码）
    StrictStr, StrictInt, StrictBool, StrictFloat,  # 严格模式（不做类型转换）
    PositiveInt, NegativeInt, NonNegativeInt, NonPositiveInt,
    PositiveFloat, NegativeFloat,
    conint, constr, confloat, condecimal, conlist, conset,  # 运行时构造带约束的类型
)

class Model(BaseModel):
    email: EmailStr
    website: HttpUrl
    password: SecretStr              # print(m.password) → SecretStr('**********')
    api_key: SecretBytes
    age: PositiveInt                 # > 0
    name: constr(min_length=1, max_length=50)   # 等价于 str + Field(min_length=..., max_length=...)
    items: conlist(int, min_length=1, max_length=10)
```

**`SecretStr` 的用法**：

```python
m = Model(password="hunter2", ...)
print(m.password)              # SecretStr('**********')
print(m.password.get_secret_value())   # hunter2
print(m.model_dump())          # {'password': SecretStr('**********'), ...}
print(m.model_dump_json())     # {"password": "**********", ...}
```

### 5.3 嵌套模型

```python
class Address(BaseModel):
    street: str
    city: str

class User(BaseModel):
    name: str
    address: Address                 # 嵌套模型
    friends: list[Address] = []      # 模型列表

# 自动递归校验
u = User.model_validate({
    "name": "alice",
    "address": {"street": "Main St", "city": "NYC"},
    "friends": [{"street": "2nd Ave", "city": "NYC"}],
})
```

### 5.4 自定义类型（`Annotated`）

```python
from typing import Annotated
from pydantic import AfterValidator, BeforeValidator, Field

def validate_even(v: int) -> int:
    if v % 2 != 0:
        raise ValueError("must be even")
    return v

EvenInt = Annotated[int, AfterValidator(validate_even)]

class Model(BaseModel):
    x: EvenInt                       # 只能是偶数

# 组合约束
PositiveEvenInt = Annotated[int, Field(gt=0), AfterValidator(validate_even)]
```

### 5.5 自定义类型（`__get_pydantic_core_schema__`）

```python
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

class MyType:
    def __init__(self, value: str):
        self.value = value

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, cls): return v
        if not isinstance(v, str): raise ValueError("must be str")
        return cls(v)
```

---

## 六、模型配置（ConfigDict）

```python
from pydantic import BaseModel, ConfigDict

class Model(BaseModel):
    model_config = ConfigDict(
        # ── 字段名与别名 ──────────────────────
        populate_by_name=True,         # 允许用字段名或别名（v1 是 allow_population_by_field_name）
        str_to_lower=True,             # 所有字符串自动转小写
        str_to_upper=True,             # 所有字符串自动转大写
        str_strip_whitespace=True,     # 所有字符串自动去首尾空格

        # ── 额外字段 ──────────────────────────
        extra="forbid",                # 多传字段 → 报错（默认 "ignore" 静默丢弃）
        # extra="allow"                # 多传字段 → 保留
        # extra="ignore"               # 多传字段 → 丢弃（默认）

        # ── 校验行为 ──────────────────────────
        validate_assignment=True,      # 赋值时也校验（默认只在创建时校验）
        validate_default=True,         # 默认值也要校验
        strict=True,                   # 严格模式（不做类型转换，见下面）
        revalidate_instances="always", # 嵌套模型实例也重新校验

        # ── 序列化 ────────────────────────────
        ser_json_timedelta="iso8601",  # timedelta 序列化为 ISO 8601
        ser_json_bytes="utf8",         # bytes 序列化为 UTF-8 字符串
        frozen=True,                   # 模型不可变（哈希、赋值报错）

        # ── ORM 集成 ──────────────────────────
        from_attributes=True,          # 允许从对象属性读取（v1 是 orm_mode）

        # ── JSON Schema ───────────────────────
        json_schema_extra={            # 给 JSON Schema 加额外字段
            "examples": [{"name": "alice"}]
        },
        title="My Model",              # JSON Schema 标题
        json_schema_mode_override=None,

        # ── 其他 ──────────────────────────────
        arbitrary_types_allowed=True,  # 允许任意类型（不校验）
        use_enum_values=True,          # 枚举字段存值而不是枚举对象
        validate_by_name=True,         # 2.11+ 新选项
    )
```

**v1 的 `class Config` 在 v2 里已废弃**，但还能用（会报 DeprecationWarning）：

```python
# v1 老写法（不推荐）
class Config:
    orm_mode = True
    extra = "forbid"
```

---

## 七、校验器（Validators）

### 7.1 `@field_validator`（单字段校验）

```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str
    age: int

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()

    @field_validator("age")
    @classmethod
    def age_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("age must be >= 0")
        return v

    # 校验多个字段
    @field_validator("name", "age")
    @classmethod
    def check_all(cls, v):
        ...

    # 校验所有字段
    @field_validator("*")
    @classmethod
    def check_everything(cls, v):
        ...
```

**模式（mode）**：

```python
@field_validator("x", mode="before")    # 类型转换前校验（拿到原始输入）
@field_validator("x", mode="after")     # 类型转换后校验（默认，拿到 Python 值）
```

### 7.2 `@model_validator`（整模型校验）

```python
from pydantic import BaseModel, model_validator

class Password(BaseModel):
    password: str
    confirm: str

    @model_validator(mode="before")
    @classmethod
    def preprocess(cls, data):
        # 在字段校验之前运行，data 是原始输入（dict / str / 对象）
        if isinstance(data, str):
            return {"password": data, "confirm": data}
        return data

    @model_validator(mode="after")
    def check_match(self):
        # 在所有字段校验之后运行，self 是已经构造好的实例
        if self.password != self.confirm:
            raise ValueError("passwords do not match")
        return self
```

**三种模式**：

- `mode="before"` —— 字段校验前，拿到原始输入
- `mode="after"` —— 字段校验后，拿到实例（最常用）
- `mode="wrap"` —— 包裹整个校验过程，可以自定义校验逻辑

### 7.3 `Annotated` + `AfterValidator` / `BeforeValidator`

```python
from typing import Annotated
from pydantic import AfterValidator, BeforeValidator, BaseModel

def strip_and_lower(v: str) -> str:
    return v.strip().lower()

Name = Annotated[str, AfterValidator(strip_and_lower)]

class User(BaseModel):
    name: Name

u = User(name="  ALICE  ")
print(u.name)    # alice
```

### 7.4 v1 → v2 迁移对照

| v1 | v2 |
|---|---|
| `@validator("x")` | `@field_validator("x")` + `@classmethod` |
| `@validator("x", pre=True)` | `@field_validator("x", mode="before")` |
| `@validator("x", always=True)` | `@field_validator("x")` + `validate_default=True` |
| `@root_validator` | `@model_validator(mode="after")` |
| `@root_validator(pre=True)` | `@model_validator(mode="before")` |

---

## 八、序列化与反序列化

### 8.1 对象 → 字典 / JSON

```python
m = User(id=1, name="alice")

# 转字典
d = m.model_dump()                          # {'id': 1, 'name': 'alice'}
d = m.model_dump(mode="json")               # datetime 等转成 JSON 兼容字符串
d = m.model_dump(include={"id", "name"})    # 只包含指定字段
d = m.model_dump(exclude={"password"})      # 排除指定字段
d = m.model_dump(exclude_unset=True)        # 只导出显式设置过的字段（PATCH 必备）
d = m.model_dump(exclude_defaults=True)     # 排除等于默认值的字段
d = m.model_dump(exclude_none=True)         # 排除 None 字段
d = m.model_dump(by_alias=True)             # 用别名作为 key

# 转 JSON 字符串
s = m.model_dump_json()
s = m.model_dump_json(indent=2)             # 美化输出
s = m.model_dump_json(exclude={"password"})
```

**`exclude_unset=True` 的重要性**（PATCH 接口必备）：

```python
class TaskUpdate(BaseModel):
    content: str | None = None
    done: bool | None = None

# 客户端只传了 content，没传 done
update = TaskUpdate.model_validate({"content": "new"})
update.model_dump()                          # {'content': 'new', 'done': None}
update.model_dump(exclude_unset=True)        # {'content': 'new'}  ← 只有这个能区分"没传"和"传了 null"
```

### 8.2 字典 / JSON → 对象

```python
# 从字典
u = User.model_validate({"id": 1, "name": "alice"})
u = User.model_validate({"id": 1, "name": "alice"}, strict=True)   # 严格模式

# 从 JSON 字符串
u = User.model_validate_json('{"id": 1, "name": "alice"}')

# 从对象属性（ORM 集成）
u = User.model_validate(orm_obj, from_attributes=True)

# 从字符串（所有值都当字符串处理）
u = User.model_validate_strings({"id": "1", "name": "alice"})

# 上下文传递（校验器里能拿到）
u = User.model_validate(data, context={"user_id": 123})
```

### 8.3 自定义序列化

```python
from pydantic import BaseModel, field_serializer, computed_field

class User(BaseModel):
    first_name: str
    last_name: str
    password: str

    @computed_field                        # 计算字段（序列化时自动包含）
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @field_serializer("password")          # 自定义某字段的序列化
    def mask_password(self, v: str) -> str:
        return "*" * len(v)

u = User(first_name="alice", last_name="smith", password="secret")
print(u.model_dump())
# {'first_name': 'alice', 'last_name': 'smith', 'password': '******', 'full_name': 'alice smith'}
```

---

## 九、错误处理

```python
from pydantic import BaseModel, ValidationError

class User(BaseModel):
    id: int
    name: str

try:
    User(id="x", name="")
except ValidationError as e:
    print(e)                    # 人类可读的错误信息
    print(e.errors())           # 结构化错误列表
    print(e.json())             # JSON 格式的错误
    print(e.error_count())      # 错误数量

# e.errors() 的结构
[
    {
        "type": "int_parsing",           # 错误类型（机器可读）
        "loc": ("id",),                  # 字段路径（元组）
        "msg": "Input should be a valid integer",  # 错误说明
        "input": "x",                    # 原始输入
        "url": "https://errors.pydantic.dev/...",  # 文档链接
    },
    {
        "type": "string_too_short",
        "loc": ("name",),
        "msg": "String should have at least 1 character",
        "input": "",
        "ctx": {"min_length": 1},        # 约束上下文
    },
]
```

**常见错误类型**：

- `missing` —— 缺少必填字段
- `int_parsing` / `float_parsing` / `bool_parsing` —— 类型转换失败
- `string_type` / `int_type` —— 类型错误（严格模式）
- `string_too_short` / `string_too_long` —— 长度不符
- `greater_than_equal` / `less_than_equal` —— 范围不符
- `value_error` —— 自定义校验器抛的 ValueError
- `extra_forbidden` —— 多传了字段（`extra="forbid"`）

---

## 十、继承与 Mixin

```python
class TimestampMixin(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class User(TimestampMixin, BaseModel):
    id: int
    name: str

# 多重继承
class Admin(User, PermissionsMixin):
    ...
```

**注意**：Mixin 也要继承 `BaseModel`，否则字段不会被识别。

---

## 十一、泛型模型

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class Response(BaseModel, Generic[T]):
    code: int
    message: str
    data: T | None = None

class User(BaseModel):
    id: int
    name: str

# 具体化
UserResponse = Response[User]
r = UserResponse(code=0, message="ok", data=User(id=1, name="alice"))

# 列表
UserListResponse = Response[list[User]]
r = UserListResponse(code=0, message="ok", data=[User(id=1, name="alice")])
```

---

## 十二、联合类型与 Discriminated Union

```python
from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field, Discriminator, Tag

class Cat(BaseModel):
    type: Literal["cat"] = "cat"
    meow: str

class Dog(BaseModel):
    type: Literal["dog"] = "dog"
    bark: str

# 自动判别（推荐）
Pet = Annotated[Union[Cat, Dog], Field(discriminator="type")]

class Owner(BaseModel):
    pet: Pet

o = Owner.model_validate({"pet": {"type": "cat", "meow": "hello"}})
# 自动识别为 Cat

# 手动判别
def get_discriminator(v):
    if isinstance(v, dict):
        return v.get("type")
    return getattr(v, "type", None)

Pet = Annotated[
    Union[Annotated[Cat, Tag("cat")], Annotated[Dog, Tag("dog")]],
    Discriminator(get_discriminator),
]
```

**好处**：错误信息更精确（不会把 Cat 的字段错误报成 Dog 的），性能更好（不用逐个尝试）。

---

## 十三、严格模式 vs 宽松模式

```python
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

class Lenient(BaseModel):
    age: int
    name: str

Lenient(age="25", name=123)      # OK，自动转换

class Strict(BaseModel):
    model_config = ConfigDict(strict=True)
    age: int
    name: str

Strict(age="25", name=123)       # ValidationError，不做类型转换

# 单字段严格
class Mixed(BaseModel):
    age: StrictInt                 # 严格
    name: str                      # 宽松
```

**什么时候用严格模式**：

- 外部输入（API 请求体）用宽松模式（容错）
- 内部数据传递用严格模式（防 bug）
- 配置文件解析用严格模式（及早发现错误）

---

## 十四、JSON Schema 生成

```python
class User(BaseModel):
    id: int
    name: str = Field(min_length=1, description="用户名")
    email: EmailStr | None = None

print(User.model_json_schema())
# {
#     "title": "User",
#     "type": "object",
#     "properties": {
#         "id": {"title": "Id", "type": "integer"},
#         "name": {"title": "Name", "minLength": 1, "type": "string", "description": "用户名"},
#         "email": {"anyOf": [{"type": "string", "format": "email"}, {"type": "null"}]}
#     },
#     "required": ["id", "name"]
# }

# 带 ref 的 schema（嵌套模型）
print(User.model_json_schema(ref_template="#/definitions/{model}"))

# 序列化 schema（和校验 schema 略有不同）
print(User.model_json_schema(mode="serialization"))
```

**FastAPI 就是靠这个生成 OpenAPI 文档的**。

---

## 十五、pydantic-settings（配置管理）

```bash
pip install pydantic-settings
```

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",                 # 从 .env 文件读
        env_file_encoding="utf-8",
        env_prefix="APP_",               # 环境变量前缀（APP_DATABASE_URL）
        case_sensitive=False,            # 环境变量名不区分大小写
        extra="ignore",                  # 忽略多余的环境变量
    )

    database_url: str
    debug: bool = False
    port: int = 8000
    secret_key: str

settings = Settings()                    # 自动从环境变量 / .env 读
print(settings.database_url)
```

**优先级**：`__init__` 参数 > 环境变量 > `.env` 文件 > 默认值

---

## 十六、与 FastAPI 集成

```python
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI()

class TaskCreate(BaseModel):
    content: str = Field(min_length=1, max_length=200)
    done: bool = False

class TaskOut(BaseModel):
    id: int
    content: str
    done: bool

@app.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(task: TaskCreate):
    # FastAPI 自动：
    # 1. 从请求体解析 JSON
    # 2. 用 TaskCreate 校验（失败返回 422）
    # 3. 把 task 对象传给你的函数
    # 4. 用 TaskOut 序列化返回值（过滤多余字段）
    # 5. 生成 OpenAPI 文档
    return {"id": 1, **task.model_dump()}
```

**关键点**：

- 请求体模型和响应体模型分开（`TaskCreate` vs `TaskOut`）
- `response_model` 会过滤掉返回值里多余的字段
- 校验失败自动返回 422，错误结构是 Pydantic 的 `ValidationError.errors()`

---

## 十七、与 SQLAlchemy 集成

```python
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# SQLAlchemy 模型
class UserORM(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(120))

# Pydantic 模型
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # ← 关键：允许从对象属性读取

    id: int
    name: str
    email: str | None = None

# 转换
orm_user = session.get(UserORM, 1)
pydantic_user = UserOut.model_validate(orm_user)      # 自动从 orm_user 的属性读取
```

**`from_attributes=True` 的作用**：让 Pydantic 用 `getattr(obj, field_name)` 读取字段，而不是只接受 dict。

---

## 十八、性能优化

1. **用 `model_construct` 跳过校验**（数据已确认合法时）：

    ```python
    u = User.model_construct(id=1, name="alice")   # 不校验，快 10 倍
    ```

2. **用 `__slots__`**（减少内存）：

    ```python
    class User(BaseModel):
        model_config = ConfigDict(extra="forbid")
        __slots__ = ()   # Pydantic v2 已经用了 slots，不用手动加
    ```

3. **用 `frozen=True`**（不可变对象可哈希、可缓存）：

    ```python
    class User(BaseModel):
        model_config = ConfigDict(frozen=True)
    ```

4. **避免 `Any` 类型**（不校验 = 慢）

5. **用 `model_dump(mode="json")` 而不是手动转字典**

6. **批量校验用 `TypeAdapter`**：

    ```python
    from pydantic import TypeAdapter

    adapter = TypeAdapter(list[User])
    users = adapter.validate_python(data_list)   # 比逐个 User.model_validate 快
    ```

---

## 十九、常见坑清单

| 坑 | 解决 |
|---|---|
| **可变默认值** | 用 `Field(default_factory=list)`，不要 `= []` |
| **`exclude_unset` 忘用** | PATCH 接口必须用，否则分不清"没传"和"传了 null" |
| **`extra="ignore"` 静默丢弃** | 改成 `extra="forbid"`，拼错字段名直接报错 |
| **`validate_assignment` 没开** | 赋值时不校验，`u.age = -1` 不会报错 |
| **`from_attributes` 没开** | 从 ORM 对象读取时报错 |
| **`SecretStr` 直接打印** | 用 `.get_secret_value()` 才能拿到真实值 |
| **`datetime` 时区** | 默认 naive，生产用 `datetime.now(timezone.utc)` |
| **`Decimal` 精度** | JSON 里是字符串，`model_dump(mode="json")` 会转成 str |
| **嵌套模型不重新校验** | 用 `revalidate_instances="always"` |
| **`model_validator(mode="after")` 里改字段** | 要用 `object.__setattr__(self, "x", v)`（如果 frozen=True） |
| **`field_validator` 忘记 `@classmethod`** | v2 必须加，否则不生效 |
| **`Optional[X]` 不等于"可选"** | `Optional[X]` 只是 `X \| None`，字段还是必填；要可选得加默认值 `= None` |
| **`alias` 和字段名混用** | 用 `populate_by_name=True` 允许两种都行 |
| **`ValidationError` 在 FastAPI 里被吞** | 自定义 exception handler 统一处理 |

---

## 二十、完整示例：一个生产级模型

```python
from datetime import datetime, timezone
from typing import Literal, Annotated
from pydantic import (
    BaseModel, ConfigDict, Field, EmailStr,
    field_validator, model_validator, computed_field, field_serializer,
)

Password = Annotated[str, Field(min_length=8, max_length=100)]
Username = Annotated[str, Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")]

class UserCreate(BaseModel):
    """注册请求体"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: Username
    email: EmailStr
    password: Password
    password_confirm: Password
    age: int = Field(ge=0, le=150)
    role: Literal["user", "admin"] = "user"

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("passwords do not match")
        return self

class UserOut(BaseModel):
    """响应体"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    role: str
    created_at: datetime
    is_active: bool = True

    @computed_field
    @property
    def display_name(self) -> str:
        return f"{self.username} ({self.role})"

    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat()

class UserUpdate(BaseModel):
    """PATCH 请求体"""
    model_config = ConfigDict(extra="forbid")

    username: Username | None = None
    email: EmailStr | None = None
    age: int | None = Field(default=None, ge=0, le=150)
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_at_least_one(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError("at least one field must be provided")
        return self
```

---

## 附录：本项目内的 Pydantic 用法示例

以下是本仓库（`e:\python_learn`）里已经存在的 Pydantic 使用范例，可作为对照参考：

| 模块 | 用途 | 用到的 API |
|---|---|---|
| [todolist pydantic.py](./todolist%20pydantic.py) | 单机脚本版的 Task 数据校验 | `BaseModel` / `ConfigDict(validate_assignment=True)` / `Field` / `ValidationError` / `@model_validator(mode="before")` |
| [todo_api/schemas.py](./todo_api/schemas.py) | FastAPI 的请求体/响应体定义 | `BaseModel` / `ConfigDict(extra="forbid")` / `Field(min_length=..., max_length=..., description=...)` |
| [todo_api/deps.py](./todo_api/deps.py) | FastAPI 依赖注入里的数据结构 | `BaseModel` / `Field(ge=0, description=...)` |

**分层规律**：pydantic 只出现在**接口边界**（HTTP 请求/响应）和**外部数据边界**（读 JSON 文件），持久层（`day15_orm`、`day16_crud`、`day17_relationship`）完全不用它——那一层是 SQLAlchemy 的活。

---

## 参考

- 官方文档：<https://docs.pydantic.dev/latest/>
- v1 → v2 迁移指南：<https://docs.pydantic.dev/latest/migration/>
- 错误类型索引：<https://errors.pydantic.dev/>
- 本项目锁定的版本：`pydantic==2.13.5`（见 [requirements.txt](./requirements.txt)）
