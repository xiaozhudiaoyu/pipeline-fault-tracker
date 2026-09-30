# 测试公共夹具（conftest.py）—— P1 测试体系的地基。
#
# 三件核心事（对应阶段二计划 P1 验收口径）：
#   ① 单元用内存库：DATABASE_URL 环境变量在任何 app 导入【之前】覆盖为 sqlite:///:memory:，
#      app.database 的模块级 engine 因此绑定内存库，全程不碰开发库 fault_tracker.db；
#   ② 集成走 ASGI：httpx AsyncClient + ASGITransport 直接调 app，不起 uvicorn、不占端口；
#   ③ 依赖覆盖隔离：app.dependency_overrides 把 get_db 换成测试 session，
#      请求链路与测试断言操作同一个内存库会话。
#
# 为什么环境变量必须在 import app 之前设置？
#   app/config.py 的 settings 是模块级单例（import 时即读 .env 固化），
#   app/database.py 的 engine 同样是模块级创建。导入顺序错了就会绑到开发库。
#   pydantic-settings 的优先级：环境变量 > .env 文件 > 字段默认值（已核实 config.py）。

import os

# ---- ① 环境隔离：必须先于任何 app.* 导入 ----
# 测试库连接串：默认内存 SQLite（零依赖、无需外部服务，与引入 PG 前行为完全一致）；
# 设 TEST_DATABASE_URL 可整套切到 PostgreSQL —— P3 验证「同一套测试跑两种方言」，例如：
#   TEST_DATABASE_URL=postgresql+psycopg://pft:pft_pass@localhost:5433/pft uv run pytest
# 优先级：显式 TEST_DATABASE_URL > 默认内存 SQLite；该值同时用于 app 的 DATABASE_URL 与下面的 test_engine。
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["DB_ECHO"] = "false"

from collections.abc import AsyncIterator, Iterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import database  # noqa: E402  （env 已覆盖，它的 engine 也指向内存库，但测试不用它，见下）
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


# ---- 测试专用 engine：按方言选择连接参数与连接池 ----
# 为什么不直接用 app.database.engine？
#   SQLite 的 :memory: 库是「每个连接一份独立数据」；默认连接池会发放多个连接，
#   建表的连接和查询的连接可能不是同一个 → 数据互相看不见。
#   StaticPool 强制所有 session 复用同一连接，共享同一份内存数据。
#   PostgreSQL 是服务端库，数据对所有连接可见，用默认连接池即可，
#   且【不能】传 SQLite 专属的 check_same_thread（psycopg 不认，会 TypeError）——与 database.py 的方言分支同理。
#   （app 自己的 engine 在测试中不承担读写：get_db 已被依赖覆盖，init_models 不触发。）
if _TEST_DB_URL.startswith("sqlite"):
    test_engine: Engine = create_engine(
        _TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    test_engine: Engine = create_engine(_TEST_DB_URL)

# ---- 测试 session 工厂：参数与 app.database.SessionLocal 完全一致 ----
TestingSessionLocal = sessionmaker(
    bind=test_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """每个测试独享干净表结构：先 drop_all 再 create_all，用完再 drop_all。

    「测试可重复跑、无脏数据残留」靠它保证：任何测试看到的就是空库，
    不依赖执行顺序，单跑/乱序跑结果一致。
    """
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(test_engine)


@pytest.fixture
async def client(db_session: Session) -> AsyncIterator[httpx.AsyncClient]:
    """集成测试客户端：ASGITransport 直连 app + get_db 依赖覆盖到测试 session。

    说明：ASGITransport 不触发 lifespan（不自动建表）——建表由 db_session
    显式完成，反而更可控：表结构何时建、何时清，测试自己说了算。
    """

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[database.get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """anyio 的 pytest 插件要求声明后端；本项目 async 测试全部跑 asyncio。"""
    return "asyncio"
