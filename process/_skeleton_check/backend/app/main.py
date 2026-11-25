# FastAPI 应用入口：创建 app、配置 CORS、启动时自动建表、注册全站错误处理。
#
# 启动（在 backend/ 目录下，激活 .venv 后运行）：
#     uvicorn app.main:app --reload --port 8000
#
# 启动后浏览器打开 http://127.0.0.1:8000/docs 查看 Swagger 交互式文档。
#
# 本骨架不含业务路由（无 models/schemas/crud/routers），只提供可启动的最小技术框架。
# 业务接入步骤见技能 SKILL.md「业务接入指南」：先加模型，再加 schemas/crud/routers，
# 最后在此挂载路由与 openapi_tags。

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_models
from .exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期钩子：启动时建表，关闭时清理。

    init_models() 调用 Base.metadata.create_all(checkfirst=True)：
      表不存在则创建，已存在则跳过 —— 可反复重启不报错。
      骨架阶段没有模型，此调用为空操作；业务模型接入后自动生效。
      注意它【不会】修改已存在的表结构（结构演进走 Alembic）。
    """
    # ---- 启动 ----
    init_models()
    yield
    # ---- 关闭（SQLite 连接由 engine 池管理，无需特殊清理）----


app = FastAPI(
    title="演示系统 API",
    version="0.1.0",
    description=(
        "演示系统后端。"
        "错误响应统一为 {code, message, details} 结构。"
    ),
    lifespan=lifespan,
    # 业务接入：补充 openapi_tags，如 {"name": "books", "description": "..."}，
    # name 必须与各 router 的 tags 一字不差。
)

# 注册全站错误处理（必须在 app 创建之后、路由生效之前调用）。
# 四类异常（校验错 / HTTPException / 领域异常 / 其他 bug）在 exceptions.py 集中定义，
# 所有接口的错误响应统一为 {code, message, details} 结构。
register_exception_handlers(app)

# ---- CORS 中间件 ----
# 前端 Vite 开发服务器跑在 5173 端口，与后端 8000 端口不同源，浏览器会拦截跨域请求。
# allow_origins 从配置读取（.env 的 CORS_ORIGINS），生产环境应收紧为实际前端域名。
# allow_credentials=True 允许携带 Cookie（模板暂无认证，预留）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 业务接入：挂载路由 ----
# 在 routers/ 下建模块（各 router 自带 /api/xxx 前缀），在此 include_router 挂载，
# 并把对应 tags 补充到上方 openapi_tags。


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
    """根路径健康检查，确认服务已启动。"""
    return {
        "message": "演示系统 API 已启动",
        "docs": "/docs",
        "health": "ok",
    }


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """专用健康检查端点（供前端或运维探活）。"""
    return {"status": "ok"}
