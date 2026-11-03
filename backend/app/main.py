# FastAPI 应用入口：创建 app、配置 CORS、启动时自动建表、挂载业务路由。
#
# 启动（在 backend/ 目录下，激活 .venv 后运行）：
#     uvicorn app.main:app --reload --port 8000
#
# 启动后浏览器打开 http://127.0.0.1:8000/docs 查看 Swagger 交互式文档。
#
# ── FastAPI 语法心智模型（同 python_learn/todo_api/main.py）─────────────
# 写"普通 Python 函数 + 类型注解"，框架靠【装饰器】把函数变成 HTTP 接口，
#   再靠【类型注解】在运行时自动完成 取参数 → 校验 → 序列化 → 生成文档。
# 看懂任意接口三步：① 装饰器 = 方法+路径；② 参数 = 取值来源；③ 返回值 = 响应体。
# ──────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_models
from .exceptions import register_exception_handlers
from .routers import auth, faults, pipelines


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期钩子：启动时建表，关闭时清理。

    为什么用 lifespan 而不是 @app.on_event("startup")？
      on_event 在 FastAPI 0.93+ 已标记 deprecated，lifespan 是官方推荐的替代。
      它是一个 async context manager：yield 之前 = 启动逻辑，yield 之后 = 关闭逻辑。

    init_models() 调用 Base.metadata.create_all(checkfirst=True)：
      表不存在则创建，已存在则跳过 —— 满足需求"允许采用自动建表方式初始化 SQLite"，
      且可反复重启不报错。注意它【不会】修改已存在的表结构（加字段需手工 ALTER 或 Alembic）。
    """
    # ---- 启动 ----
    init_models()
    yield
    # ---- 关闭（本项目无需特殊清理，SQLite 连接由 engine 池管理）----


# 创建应用实例。命令里的 "app.main:app" 指的就是这个名为 app 的变量。
app = FastAPI(
    title="流水线故障记录系统 API",
    version="0.1.0",
    description=(
        "记录与跟踪流水线故障的小型 Web 应用后端。"
        "业务闭环：故障登记 → 处理跟进 → 处理完成。"
        "错误响应统一为 {code, message, details} 结构。"
    ),
    lifespan=lifespan,
    # OpenAPI 文档分组说明（name 必须与各 router 的 tags 一字不差）
    openapi_tags=[
        {"name": "pipelines", "description": "流水线主数据：列表查询与创建。"},
        {"name": "faults", "description": "故障记录：登记、查询（按流水线/状态筛选）、详情、状态流转。"},
        {"name": "auth", "description": "认证（第三阶段）：登录、登出、当前用户。"},
    ],
)

# 注册全站错误处理（必须在 app 创建之后、路由生效之前调用）。
# 四类异常（校验错 / HTTPException / 领域异常 / 其他 bug）在 exceptions.py 集中定义，
# 所有接口的错误响应统一为 {code, message, details} 结构。
register_exception_handlers(app)

# ---- CORS 中间件 ----
# 前端 Vite 开发服务器跑在 5173 端口，与后端 8000 端口不同源，浏览器会拦截跨域请求。
# allow_origins 从配置读取（.env 的 CORS_ORIGINS），生产环境应收紧为实际前端域名。
# allow_credentials=True 允许携带 Cookie（本项目暂无认证，预留）。
# allow_methods=["*"] / allow_headers=["*"]：开发期放开全部方法与头，便于调试。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 挂载业务路由 ----
# 各 router 自带 /api/pipelines、/api/faults 前缀；tags 与上面 openapi_tags 对应。
app.include_router(auth.router)
app.include_router(pipelines.router)
app.include_router(faults.router)


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
    """根路径健康检查，确认服务已启动、建表已完成。"""
    return {
        "message": "流水线故障记录系统 API 已启动",
        "docs": "/docs",
        "health": "ok",
    }


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """专用健康检查端点（供前端或运维探活）。"""
    return {"status": "ok"}
