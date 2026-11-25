# FastAPI 完整用法速查

> 基于 FastAPI 0.141.1 + Uvicorn 0.52.4（本项目锁定版本，见 [requirements.txt](./requirements.txt)），从入门到能干活。所有 API 均为稳定接口。
>
> 本文档由 Qoder 会话整理落盘，作为项目内 FastAPI 用法的通用参考；附录部分给出本仓库的实证落地。

---

## 一、FastAPI 解决什么问题

Flask / Django 时代写一个接口要手动做：参数校验、类型转换、文档生成、Swagger UI、异步支持、OpenAPI schema。FastAPI 把这些全自动化了：

- **类型注解即校验**：Python 类型提示 + Pydantic 自动做请求体校验和序列化。
- **自动文档**：启动就有 `/docs`（Swagger UI）和 `/redoc`，不用写一行文档代码。
- **异步原生**：`async def` 路由直接跑在 ASGI 服务器上，天然支持高并发 IO。
- **依赖注入**：`Depends()` 系统把"认证 / 数据库 session / 分页参数"等横切关注点解耦。
- **OpenAPI 3.1**：自动生成符合规范的 schema，可直接给前端 / 测试 / SDK 生成器用。

**核心价值**：让"写一个生产级 API"从"写代码 + 写文档 + 写校验"变成"只写代码，其他自动生成"。

---

## 二、安装与生态

```bash
pip install fastapi              # 核心
pip install "fastapi[standard]"  # 带 uvicorn / httpx / jinja2 / python-multipart 等
pip install "uvicorn[standard]"  # 生产推荐（带 uvloop / httptools / watchfiles）
```

**依赖关系**：

- `starlette` —— FastAPI 的底层 ASGI 框架
- `pydantic>=2.0` —— 数据校验
- `typing-extensions` —— 类型兼容层

**常用扩展**：

| 扩展 | 用途 |
|---|---|
| `fastapi-users` | 开箱即用的认证系统 |
| `fastapi-cache2` | 响应缓存 |
| `fastapi-limiter` | 限流 |
| `fastapi-pagination` | 分页 |
| `sqlmodel` | SQLAlchemy + Pydantic 融合（FastAPI 作者出品） |
| `orjson` / `ujson` | 更快的 JSON 序列化 |
| `slowapi` | 基于 limits 的限流 |

---

## 三、最小可运行应用

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"hello": "world"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

启动：

```bash
uvicorn main:app --reload --port 8000
# 访问 http://127.0.0.1:8000/docs
```

---

## 四、路由与 HTTP 方法

```python
from fastapi import APIRouter, status

router = APIRouter(prefix="/todos", tags=["todos"])

@router.get("/", response_model=list[TodoOut])
def list_todos(): ...

@router.post("/", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
def create_todo(payload: TodoIn): ...

@router.get("/{todo_id}", response_model=TodoOut)
def get_todo(todo_id: int): ...

@router.put("/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: int, payload: TodoIn): ...

@router.patch("/{todo_id}", response_model=TodoOut)
def partial_update(todo_id: int, payload: TodoPatch): ...

@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int): ...

@router.head("/{todo_id}")
def head_todo(todo_id: int): ...

@router.options("/{todo_id}")
def options_todo(todo_id: int): ...
```

**路由装饰器参数**：

| 参数 | 作用 |
|---|---|
| `response_model` | 响应类型（Pydantic 模型），自动过滤多余字段 + 生成 OpenAPI schema |
| `response_model_exclude_unset` | 只返回显式设置的字段 |
| `response_model_exclude_none` | 排除 None 字段 |
| `status_code` | HTTP 状态码 |
| `tags` | OpenAPI 分组 |
| `summary` / `description` | OpenAPI 文档 |
| `responses` | 额外的响应示例（错误码等） |
| `deprecated` | 标记为已废弃 |
| `operation_id` | OpenAPI 操作 ID |
| `response_description` | 响应描述 |
| `name` | 路由名（用于 `url_path_for`） |
| `dependencies` | 路由级依赖（不需要返回值时用） |
| `response_class` | 自定义响应类（如 `ORJSONResponse`） |

---

## 五、路径 / 查询 / 请求体参数

### 5.1 路径参数

```python
@app.get("/items/{item_id}")
def read_item(item_id: int): ...    # 自动类型转换 + 校验

# 带约束
from fastapi import Path
@app.get("/items/{item_id}")
def read_item(item_id: int = Path(ge=1, le=1000, description="Item ID")): ...
```

### 5.2 查询参数

```python
# 单值
@app.get("/items/")
def read_items(skip: int = 0, limit: int = 10): ...

# 多值（列表）
@app.get("/items/")
def read_items(tags: list[str] | None = None): ...
# /items/?tags=a&tags=b

# 带校验
from fastapi import Query
@app.get("/items/")
def read_items(
    q: str | None = Query(None, min_length=3, max_length=50, pattern="^search"),
    limit: int = Query(10, ge=1, le=100),
): ...
```

### 5.3 请求体（Pydantic 模型）

```python
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float
    tags: list[str] = []

@app.post("/items/")
def create_item(item: Item): ...        # 自动解析 JSON body

# 多个 body 参数（需要显式 embed）
@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item, user: User): ...
# body: {"item": {...}, "user": {...}}

# 单值 body（需要 Body(...)）
from fastapi import Body
@app.post("/items/")
def create_item(name: str = Body(..., embed=True)): ...
```

### 5.4 Header / Cookie

```python
from fastapi import Header, Cookie

@app.get("/items/")
def read_items(
    x_token: str | None = Header(None, alias="X-Token"),
    session_id: str | None = Cookie(None),
): ...
```

### 5.5 表单（`application/x-www-form-urlencoded`）

```python
from fastapi import Form

@app.post("/login/")
def login(username: str = Form(...), password: str = Form(...)): ...
```

### 5.6 文件上传（`multipart/form-data`）

```python
from fastapi import File, UploadFile

@app.post("/upload/")
def upload(file: UploadFile = File(...)):
    contents = file.file.read()
    return {"filename": file.filename, "size": len(contents)}

# 多文件
@app.post("/upload/")
def upload(files: list[UploadFile] = File(...)): ...

# 文件 + 表单字段
@app.post("/upload/")
def upload(file: UploadFile = File(...), description: str = Form(...)): ...
```

### 5.7 参数位置优先级

FastAPI 按这个顺序判断参数来源：

1. 路径参数（在路径模板里出现）
2. Pydantic 模型 → 请求体
3. `File(...)` / `Form(...)` / `UploadFile` → 表单/文件
4. `Header(...)` / `Cookie(...)` → 对应位置
5. 其他标量（`int` / `str` / `bool` / `float`）→ 查询参数
6. `Body(...)` → 请求体

---

## 六、Pydantic 请求与响应模型

### 6.1 基本用法

```python
from pydantic import BaseModel, Field, EmailStr

class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr

@app.post("/users/", response_model=UserOut, status_code=201)
def create_user(user: UserIn):
    # user.password 不会被返回（response_model 过滤）
    return db_user
```

### 6.2 `response_model` 的价值

- **过滤多余字段**：即使返回了 ORM 对象，也只会序列化 `response_model` 里声明的字段。
- **自动校验**：响应不符合 schema 会抛 `ResponseValidationError`。
- **生成 OpenAPI**：Swagger 文档自动显示响应结构。
- **类型安全**：IDE 补全 + mypy / pyright 检查。

### 6.3 `response_model_exclude_unset` / `_exclude_none`

```python
@app.get("/items/{id}", response_model=Item, response_model_exclude_unset=True)
def get_item(id: int): ...
# 只返回显式设置的字段，未设置的字段不出现在 JSON 里
```

### 6.4 嵌套模型

```python
class Address(BaseModel):
    city: str
    zip_code: str

class User(BaseModel):
    name: str
    addresses: list[Address]

# 请求体自动校验嵌套结构
```

### 6.5 继承与 Mixin

```python
class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime

class UserOut(TimestampMixin):
    id: int
    name: str
```

### 6.6 泛型响应（分页）

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

@app.get("/users/", response_model=Page[UserOut])
def list_users(): ...
```

---

## 七、依赖注入（`Depends`）

### 7.1 基本用法

```python
from fastapi import Depends

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/items/")
def read_items(db: Session = Depends(get_db)):
    return db.query(Item).all()
```

### 7.2 依赖的三种形态

```python
# 1. 函数依赖
def common_params(q: str | None = None, limit: int = 10):
    return {"q": q, "limit": limit}

@app.get("/items/")
def read_items(params: dict = Depends(common_params)): ...

# 2. 类依赖（推荐，可复用 + 可测试）
class Pagination:
    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size

@app.get("/items/")
def read_items(p: Pagination = Depends()): ...

# 3. yield 依赖（带清理）
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 7.3 依赖嵌套

```python
def get_user(token: str = Header(...)):
    user = verify_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

def get_user_permissions(user: User = Depends(get_user)):
    return db.query(Permission).filter_by(user_id=user.id).all()

@app.get("/items/")
def read_items(perms: list[Permission] = Depends(get_user_permissions)): ...
```

### 7.4 全局依赖

```python
app = FastAPI(dependencies=[Depends(log_request)])

# 或路由级
router = APIRouter(dependencies=[Depends(verify_api_key)])

# 或单个路由
@app.get("/items/", dependencies=[Depends(rate_limit)])
def read_items(): ...
```

### 7.5 依赖覆盖（测试必备）

```python
from fastapi.testclient import TestClient

app.dependency_overrides[get_db] = lambda: fake_db
client = TestClient(app)
```

### 7.6 `Depends` vs `Security`

`Security` 是 `Depends` 的别名，额外支持 `scopes` 参数（OAuth2 权限范围）：

```python
from fastapi import Security

def get_current_user(scopes: list[str] = Security(oauth2_scheme, scopes=["read"])):
    ...
```

---

## 八、中间件

### 8.1 自定义中间件

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class LogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.3f}s)")
        return response

app.add_middleware(LogMiddleware)
```

### 8.2 纯 ASGI 中间件（性能更好）

```python
class PureASGIMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # 处理请求
            pass
        await self.app(scope, receive, send)

app.add_middleware(PureASGIMiddleware)
```

### 8.3 中间件执行顺序

**后添加的先执行**（洋葱模型）：

```python
app.add_middleware(A)    # A 在外层
app.add_middleware(B)    # B 在内层
# 请求：A → B → 路由；响应：路由 → B → A
```

---

## 九、CORS

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # 或 ["*"]（生产慎用）
    allow_credentials=True,
    allow_methods=["*"],                       # GET / POST / PUT / DELETE ...
    allow_headers=["*"],                       # Content-Type / Authorization ...
    expose_headers=["X-Custom-Header"],        # 允许浏览器读取的响应头
    max_age=600,                               # 预检请求缓存秒数
)
```

**注意**：`allow_origins=["*"]` + `allow_credentials=True` 会被浏览器拒绝（规范冲突）。要么用具体域名，要么关掉 credentials。

---

## 十、异常处理

### 10.1 内置异常

```python
from fastapi import HTTPException, status

@app.get("/items/{id}")
def get_item(id: int):
    item = db.get(Item, id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
            headers={"X-Error": "not_found"},
        )
    return item
```

### 10.2 自定义异常 + 处理器

```python
class BizError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )
```

### 10.3 覆盖 Pydantic 校验错误

```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "参数校验失败", "errors": exc.errors()},
    )
```

### 10.4 全局异常兜底

```python
@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
```

---

## 十一、生命周期（lifespan）

### 11.1 现代写法（推荐）

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    app.state.db = await init_db()
    app.state.redis = await aioredis.from_url("redis://localhost")
    yield
    # shutdown
    await app.state.db.close()
    await app.state.redis.close()

app = FastAPI(lifespan=lifespan)
```

### 11.2 旧写法（已废弃但仍可用）

```python
@app.on_event("startup")
async def startup(): ...

@app.on_event("shutdown")
async def shutdown(): ...
```

### 11.3 在依赖中访问 app.state

```python
def get_db(request: Request):
    return request.app.state.db
```

---

## 十二、路由组织（`APIRouter`）

### 12.1 拆分模块

```python
# routers/todos.py
from fastapi import APIRouter
router = APIRouter(prefix="/todos", tags=["todos"])

@router.get("/")
def list_todos(): ...

# routers/users.py
router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
def list_users(): ...

# main.py
from fastapi import FastAPI
from routers import todos, users

app = FastAPI()
app.include_router(todos.router)
app.include_router(users.router)
```

### 12.2 路由级依赖

```python
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],    # 整个路由组都要管理员权限
)
```

### 12.3 路由级响应模型

```python
router = APIRouter(
    responses={404: {"description": "Not found"}},    # 所有路由共享的额外响应
)
```

---

## 十三、OpenAPI / Swagger 文档定制

### 13.1 应用级元信息

```python
app = FastAPI(
    title="My API",
    description="A production-grade API",
    version="1.0.0",
    terms_of_service="https://example.com/terms",
    contact={"name": "Support", "email": "support@example.com"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "users", "description": "用户管理"},
        {"name": "todos", "description": "待办事项"},
    ],
)
```

### 13.2 路由级文档

```python
@app.get(
    "/items/{id}",
    summary="获取单个 Item",
    description="根据 ID 返回 Item 详情。",
    response_description="Item 对象",
    responses={
        404: {"description": "Item 不存在"},
        200: {
            "content": {"application/json": {"example": {"id": 1, "name": "foo"}}},
        },
    },
)
def get_item(id: int): ...
```

### 13.3 自定义 Swagger UI

```python
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(docs_url=None, redoc_url=None)    # 关掉默认

@app.get("/docs", include_in_schema=False)
def custom_swagger():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )
```

### 13.4 导出 OpenAPI schema

```bash
python -c "from main import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi.json
```

---

## 十四、认证与授权

### 14.1 OAuth2 Password Flow

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your-secret"
ALGORITHM = "HS256"

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + expires_delta
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(401, "Incorrect username or password")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(401, "Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    user = get_user(username)
    if user is None:
        raise HTTPException(401, "User not found")
    return user

@app.get("/users/me")
def read_me(user: User = Depends(get_current_user)):
    return user
```

> **缺头行为（0.141.1 实测源码）**：`Authorization` 头缺失时 `OAuth2PasswordBearer` 抛 **401**（`detail="Not authenticated"`，带 `WWW-Authenticate: Bearer`，见已安装版 `fastapi/security/oauth2.py` 的 `make_not_authenticated_error()`），并非旧版流传的 403 —— 网上教程或旧代码里"缺头先 403、需要自己改 401"的差异描述，说的是 0.102 之前的旧行为。

### 14.2 API Key

```python
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != "expected-key":
        raise HTTPException(403, "Invalid API key")
    return api_key

@app.get("/items/", dependencies=[Depends(verify_api_key)])
def read_items(): ...
```

> 同样已核实（0.141.1）：`APIKeyHeader` 在**请求头缺失**时默认抛 **401**（`api_key.py` 仅引用 `HTTP_401_UNAUTHORIZED`）；上例中的 403 是校验函数对"key 存在但值不对"自己抛的业务语义，并非框架默认。

### 14.3 HTTP Basic Auth

```python
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

security = HTTPBasic()

def verify(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "secret")
    if not (correct_username and correct_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
```

### 14.4 权限控制

```python
def require_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Admin required")
    return user

@app.get("/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats(): ...
```

### 14.5 生产实现（本项目）

上面 14.1–14.4 是最小教学写法。本仓库第三阶段的实际落地在 `backend/app/auth.py`（认证 + 角色守卫）与 `backend/app/routers/auth.py`（登录/登出端点），差异点如下（依据均为代码实测）：

#### 方案骨架：HTTPBearer + JSON 登录（非 OAuth2 form）

```python
# app/auth.py：关掉框架默认报错，接管错误话术
_bearer_scheme = HTTPBearer(auto_error=False)

# routers/auth.py：登录端点收 JSON，不走 OAuth2PasswordRequestForm
@router.post("/api/auth/login")
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    ...
```

- 登录用 `POST /api/auth/login` + JSON 请求体。脱离 OAuth2 协议的 form-urlencoded 约束，代价是 Swagger UI 没有 Authorize 按钮 —— 客户端是自家 Vue，不需要标准 OAuth2 兼容性。
- `auto_error=False` 接管错误：可区分"未提供凭证 / 登录过期 / 凭证无效 / 账号不存在 / 账号停用 / 凭证已失效"六种 401 话术（框架默认只有笼统的 `Not authenticated`）。
- 密码哈希直用 `bcrypt.hashpw / checkpw`，不经 passlib（passlib 停维护，与新版 bcrypt 4.x 有兼容问题）。
- JWT（PyJWT，HS256）payload：`sub`（不可变的用户 **ID**，非用户名）、`username`、`role`、`tv`、`iat/exp`。

#### token_version 即时失效

用户表维护 `token_version` 计数器，签发时写入 payload 的 `tv`；**停用 / 改密 / 登出时 bump 一下**，此前签发的全部 token 在下一次请求即失效 —— 不用黑名单、不依赖 Redis，校验时一次查库顺带比对就够（本项目规模下的裁定）。

```python
# get_current_user 校验链（任一失败即 401）
# ① Header 形如 "Bearer xxx" → ② JWT 签名有效且未过期
# → ③ 用户仍存在 → ④ is_active → ⑤ payload.tv == user.token_version

# routers/auth.py /logout：无响应体 204，仅做 bump
crud.bump_token_version(db, user)
```

#### role 与 resource 两级权限

- **第一级 · 角色守卫（接口粒度）**：`require_roles(*roles)` 依赖工厂，内部依赖 `CurrentUser`，天然保证"先认证、再鉴权"；预置 `AdminUser / HandlerUser / HandlerOrAdminUser` 三个 `Annotated` 别名，路由签名写类型即可。
- **第二级 · 资源归属 × 状态守卫（数据行粒度）**：`can_view_fault` + 一组 `check_can_*` 纯函数（admin 看全部、handler 看分派给自己的、user 只看自己创建的）。刻意**不包装成 FastAPI 依赖**：动作端点内部要"先取 fault → 再判断 → 同事务写时间线"，拆成依赖后无法共享 session 事务，因此由 crud 层直接调用。
- 后端是最终裁判：前端隐藏按钮只优化体验，不作为安全边界。

#### 401 / 403 / 409 错误码语义

| 状态码 | 语义 | 抛出点 |
|---|---|---|
| 401 | 身份未确认，重新登录**可能**有用 | `get_current_user` 校验链①–⑤，直接抛 `HTTPException`（带 `WWW-Authenticate: Bearer`） |
| 403 | 身份已确认但不允许做，重新登录**没**用 | 路由层 `require_roles` 抛 `HTTPException(403)`；业务层抛领域异常 `PermissionDeniedError` → `app/exceptions.py` handler 翻译 |
| 409 | 身份权限都对，但与记录当前状态冲突 | `InvalidTransitionError` → 409（如 done 还去指派、待确认还去改派） |

- 409 与 422 的分界：**422 = JSON 格式本身不合格（换谁都会失败）；409 = 格式没问题、只跟这条记录当前状态打架（换条记录就成功）**。
- 403 与 404 的取舍：同一记录不同人可见 → 403（本项目非多租户隔离场景，不需要隐藏存在性）。
- crud 层只抛领域异常、不懂 HTTP（关注点分离）；带 `WWW-Authenticate` 头的 401/403 才由路由/认证层直接抛 `HTTPException`。

#### 登录防枚举

- 登录接口：用户名不存在 / 密码错误 / 账号停用，**三种失败合并为同一 401 + 同一话术"用户名或密码错误"** —— 连"账号有效但被停用"的差异也抹掉，防止攻击者按响应差异枚举有效账号。
- JWT 解码：签名错误 / 算法不匹配 / payload 非 JSON 等一律同一话术"身份凭证无效"；仅过期单独提示（对合法用户是必要信息，且不构成枚举面）。

**选型结论**：需要给外部系统按标准协议供 token（Swagger Authorize 按钮、OAuth2 SDK 对接）→ 用 14.1；自家前端的业务系统要求即时失效 + 分级权限闭环 → 用本节这套。

---

## 十五、WebSocket

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print(f"Client {client_id} disconnected")
```

**要点**：

- `await websocket.accept()` 必须先调用
- `receive_text()` / `receive_json()` / `receive_bytes()` 接收
- `send_text()` / `send_json()` / `send_bytes()` 发送
- 客户端断开时抛 `WebSocketDisconnect`

---

## 十六、后台任务（`BackgroundTasks`）

```python
from fastapi import BackgroundTasks

def send_email(email: str, message: str):
    # 耗时操作
    ...

@app.post("/notify/")
def notify(bg: BackgroundTasks, email: str):
    bg.add_task(send_email, email, "Hello")
    return {"message": "Email will be sent in background"}
```

**要点**：

- 后台任务在响应返回**之后**执行
- 不阻塞请求
- 异常不会影响响应（已返回）
- 适合发邮件 / 写日志 / 清理缓存等轻量任务
- **不适合**：需要保证执行的重任务（用 Celery / RQ / ARQ）

---

## 十七、流式响应 / SSE

### 17.1 StreamingResponse

```python
from fastapi.responses import StreamingResponse
import asyncio

async def event_generator():
    for i in range(10):
        yield f"data: chunk {i}\n\n"
        await asyncio.sleep(1)

@app.get("/stream")
def stream():
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 17.2 SSE（Server-Sent Events）

```python
from sse_starlette.sse import EventSourceResponse

@app.get("/sse")
async def sse():
    async def generator():
        for i in range(10):
            yield {"data": f"message {i}"}
            await asyncio.sleep(1)
    return EventSourceResponse(generator())
```

### 17.3 FileResponse

```python
from fastapi.responses import FileResponse

@app.get("/download/{filename}")
def download(filename: str):
    return FileResponse(f"/path/to/files/{filename}", filename=filename)
```

---

## 十八、与数据库集成（异步 Session）

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from fastapi import Depends

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

@app.get("/items/")
async def read_items(db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(Item))
    return result.all()
```

**要点**：

- 路由必须是 `async def`
- Session 用 `yield` 依赖注入，自动清理
- 所有数据库操作都要 `await`
- 懒加载不能用了，必须显式 `selectinload`

---

## 十九、测试

### 19.1 TestClient（同步）

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}
```

### 19.2 httpx AsyncClient（异步）

```python
import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_async():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
```

### 19.3 依赖覆盖（Mock 数据库）

```python
from fastapi.testclient import TestClient
from main import app, get_db

def override_get_db():
    return fake_db_session

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
```

### 19.4 测试最佳实践

- **用 pytest fixture 管理 TestClient**：避免每个测试都创建
- **用依赖覆盖 Mock 外部服务**：数据库 / Redis / 第三方 API
- **测试 OpenAPI schema**：确保文档和实现一致
- **测试错误路径**：404 / 422 / 401 / 403 都要覆盖
- **用 factory_boy 生成测试数据**：避免硬编码

---

## 二十、部署

### 20.1 Uvicorn（开发）

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 20.2 Uvicorn + Gunicorn（生产）

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**参数说明**：

- `-w 4`：4 个 worker 进程
- `-k uvicorn.workers.UvicornWorker`：用 Uvicorn 作为 ASGI worker
- `--bind 0.0.0.0:8000`：监听地址

### 20.3 Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 20.4 生产环境清单

- **HTTPS**：用 Nginx / Traefik 做反向代理 + TLS 终止
- **进程管理**：systemd / supervisor / Docker Compose
- **日志**：结构化日志（JSON）+ 日志聚合（ELK / Loki）
- **监控**：Prometheus + Grafana（用 `prometheus-fastapi-instrumentator`）
- **健康检查**：`/health` 端点（返回 DB / Redis 连接状态）
- **限流**：Nginx 层或应用层（slowapi）
- **CORS**：生产环境只允许具体域名，不用 `*`
- **环境变量**：敏感配置（DB 密码 / JWT secret）从环境变量读，不进 Git

---

## 二十一、常见坑清单

| 坑 | 解决 |
|---|---|
| **`async def` 里用同步阻塞调用** | 会阻塞事件循环。用 `run_in_executor` 或改异步库 |
| **`def` 路由里用 `await`** | 语法错误。要么改 `async def`，要么去掉 `await` |
| **`response_model` 过滤了需要的字段** | 检查 `response_model` 是否包含所有需要的字段 |
| **`Depends` 的 `yield` 依赖没清理** | 确保 `finally` 块里做清理 |
| **CORS `allow_origins=["*"]` + `allow_credentials=True`** | 浏览器拒绝。要么用具体域名，要么关 credentials |
| **路径参数类型不匹配** | `item_id: int` 但传了字符串 → 422。检查类型注解 |
| **查询参数默认值可变对象** | `tags: list[str] = []` 会共享。用 `Query(default=[])` |
| **`HTTPException` 的 `detail` 不是字符串** | 必须是字符串或可 JSON 序列化的对象 |
| **中间件里修改请求体** | Starlette 的请求体只能读一次。需要缓存 |
| **`BackgroundTasks` 里抛异常** | 不影响响应（已返回），但会记录日志。重任务用 Celery |
| **WebSocket 没调 `accept()`** | 连接会挂起。必须先 `await websocket.accept()` |
| **`lifespan` 里 `yield` 之前抛异常** | 应用启动失败。确保 startup 代码有 try/except |
| **`app.state` 在测试里没初始化** | 用 `lifespan` 或 fixture 初始化 |
| **`openapi_tags` 和路由 `tags` 不一致** | 文档分组混乱。保持同步 |
| **`response_model_exclude_unset` 和 `_exclude_none` 混淆** | `unset` = 没显式设置；`none` = 值是 None |
| **`Path` / `Query` 的约束不生效** | 检查是否用了 `Annotated[int, Path(ge=1)]`（2.0 推荐） |
| **`UploadFile` 没关** | 用 `with` 或手动 `await file.close()` |
| **`Form(...)` 和 `Body(...)` 混用** | 一个请求只能有一种 content-type |

---

## 二十二、性能优化清单

1. **用 `async def` + 异步驱动**：高并发 IO 场景必用
2. **用 `orjson` / `ujson`**：替换默认 JSON 序列化器

    ```python
    from fastapi.responses import ORJSONResponse
    app = FastAPI(default_response_class=ORJSONResponse)
    ```

3. **`response_model` 精确**：不要返回整个 ORM 对象，用 Pydantic 模型过滤
4. **`selectinload` 预加载关系**：避免 N+1 查询
5. **连接池调优**：`pool_size` / `max_overflow` / `pool_recycle`
6. **Gunicorn 多 worker**：`-w 4`（CPU 核心数 × 2 + 1）
7. **静态文件用 Nginx**：不要让 FastAPI 服务静态资源
8. **缓存热点数据**：Redis / 内存缓存
9. **`BackgroundTasks` 异步化**：发邮件 / 写日志等放后台
10. **`StreamingResponse` 大文件**：不要一次性加载到内存
11. **`gzip` 中间件**：压缩响应体

    ```python
    from fastapi.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    ```

12. **`uvloop`**：替换默认事件循环（Linux / macOS）

    ```bash
    pip install uvloop
    uvicorn main:app --loop uvloop
    ```

13. **`httptools`**：更快的 HTTP 解析器

    ```bash
    pip install httptools
    uvicorn main:app --http httptools
    ```

14. **`--workers` 多进程**：Uvicorn 也支持多 worker（但不如 Gunicorn 成熟）

---

## 附录 A：本项目内的 FastAPI 落地实证

以下是本仓库（`e:\python_learn`）里已经存在的 FastAPI 实现，可作为对照参考：

### API 主包

| 模块 | 职责 |
|---|---|
| [todo_api/main.py](./todo_api/main.py) | 应用入口：`FastAPI()` 实例、OpenAPI 元信息、路由挂载、异常处理器注册 |
| [todo_api/schemas.py](./todo_api/schemas.py) | Pydantic 接口模型：`TaskIn` / `TaskOut` / `TaskUpdate` / `ErrorOut` |
| [todo_api/exceptions.py](./todo_api/exceptions.py) | 领域异常 + 4 个异常处理器（422 定制 / HTTPException 统一 / 领域异常 / 500 兜底） |
| [todo_api/deps.py](./todo_api/deps.py) | 依赖注入示例：分页参数 / 嵌套依赖 / `yield` 资源 / 认证链 / 可选登录 / 守卫依赖 |

### 路由模块

| 模块 | 职责 |
|---|---|
| [todo_api/routers/todos.py](./todo_api/routers/todos.py) | TODO CRUD + 查询过滤 + 数据重置 |
| [todo_api/routers/users.py](./todo_api/routers/users.py) | 用户列表 |
| [todo_api/routers/errors.py](./todo_api/routers/errors.py) | 异常演示端点 |
| [todo_api/routers/depends_demo.py](./todo_api/routers/depends_demo.py) | Depends 依赖注入 6 种模式演示 |

### 一键验证脚本

| 脚本 | 覆盖内容 |
|---|---|
| [run_day11_demo.py](./run_day11_demo.py) | Depends 依赖注入 6 种模式（21 个请求） |
| [run_day12_demo.py](./run_day12_demo.py) | 异常处理 + 状态码语义化（38 个断言） |
| [run_day13_demo.py](./run_day13_demo.py) | 综合练习：查询过滤 + 数据重置 + CRUD + 错误处理（69 个断言） |

### 本项目踩过的坑（已验证）

1. **`async def` 里不能用同步阻塞调用**——[todo_api/deps.py](./todo_api/deps.py) 里的 `yield` 依赖如果用同步 Session，会阻塞事件循环。必须用 `AsyncSession`。

2. **`response_model` 过滤了 ORM 对象的多余字段**——[todo_api/schemas.py](./todo_api/schemas.py) 里的 `TaskOut` 只声明了 `id` / `content` / `done`，即使返回了完整的 ORM 对象，响应里也只有这三个字段。

3. **`Depends` 的 `yield` 依赖必须在 `finally` 里清理**——[todo_api/deps.py](./todo_api/deps.py) 里的 `get_db` 用 `yield` 返回 Session，`finally` 里调 `session.close()`，否则连接池会耗尽。

4. **`HTTPException` 的 `detail` 必须是字符串或可 JSON 序列化的对象**——[todo_api/exceptions.py](./todo_api/exceptions.py) 里的 `ErrorOut` 模型用于统一错误响应格式，`detail` 字段是字符串。

5. **路径参数类型不匹配会返回 422**——[todo_api/routers/todos.py](./todo_api/routers/todos.py) 里的 `todo_id: int`，如果传了字符串，FastAPI 自动返回 422 校验错误。

6. **`app.dependency_overrides` 在测试里 Mock 数据库**——[run_day11_demo.py](./run_day11_demo.py) 里用 `dependency_overrides` 替换 `get_db`，避免测试时连真实数据库。

### 本项目常用命令（PowerShell）

```powershell
# 启动开发服务器
.\.venv\Scripts\uvicorn.exe todo_api.main:app --reload --port 8000

# 访问 Swagger UI
# http://127.0.0.1:8000/docs

# 导出 OpenAPI schema
.\.venv\Scripts\python.exe -c "from todo_api.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi.json

# 运行测试脚本
.\.venv\Scripts\python.exe run_day13_demo.py
```

---

## 附录 B：与 Pydantic / SQLAlchemy / Alembic 的集成链路

```
┌──────────────────────────────────────────────────────────┐
│  FastAPI 路由（todo_api/routers/*.py）                    │
│    ↓ 依赖注入 Session / AsyncSession                     │
├──────────────────────────────────────────────────────────┤
│  DAO 层（day16_crud/dao.py、day17_relationship/dao.py）   │
│    ↓ select() / session.execute()                        │
├──────────────────────────────────────────────────────────┤
│  SQLAlchemy ORM 模型（day15_orm/models.py）              │
│    ↓ Base.metadata                                       │
├──────────────────────────────────────────────────────────┤
│  Alembic（day18_alembic/）                                │
│    · env.py 里 target_metadata = Base.metadata           │
│    · autogenerate 对比模型 vs 数据库                      │
│    · versions/*.py 记录 schema 演进                       │
├──────────────────────────────────────────────────────────┤
│  Pydantic 接口模型（todo_api/schemas.py）                │
│    · ConfigDict(from_attributes=True)                    │
│    · 直接吃 ORM 对象，做响应序列化                        │
└──────────────────────────────────────────────────────────┘
```

**关键集成点**：

- **FastAPI → Pydantic**：`response_model=TaskOut` 自动序列化 + 过滤多余字段 + 生成 OpenAPI 文档。
- **FastAPI → SQLAlchemy**：`Depends(get_db)` 依赖注入 Session，路由里用 `select()` 查询。
- **Pydantic → SQLAlchemy**：`ConfigDict(from_attributes=True)` 让 Pydantic 直接吃 ORM 对象。
- **SQLAlchemy → Alembic**：`Base.metadata` 是 Alembic autogenerate 的对比基准。
- **Alembic → FastAPI**：迁移脚本确保数据库 schema 和 ORM 模型一致，FastAPI 启动时不会因 schema 不匹配而报错。

---

## 参考

- 官方文档：<https://fastapi.tiangolo.com/>
- 教程：<https://fastapi.tiangolo.com/tutorial/>
- 高级用户指南：<https://fastapi.tiangolo.com/advanced/>
- API 参考：<https://fastapi.tiangolo.com/reference/>
- Starlette 文档：<https://www.starlette.io/>
- 本项目锁定的版本：`fastapi==0.141.1` + `uvicorn[standard]==0.52.4`（见 [requirements.txt](./requirements.txt)）
- 配套文档：[PYDANTIC_GUIDE.md](./PYDANTIC_GUIDE.md)、[SQLALCHEMY_GUIDE.md](./SQLALCHEMY_GUIDE.md)、[ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md)、[DEPENDENCIES.md](./DEPENDENCIES.md)
