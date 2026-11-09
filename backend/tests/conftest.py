# 测试公共夹具（conftest.py）—— P1 测试体系的地基 + 第三阶段认证注入。
#
# 三件核心事（对应阶段二计划 P1 验收口径）：
#   ① 单元用内存库：DATABASE_URL 环境变量在任何 app 导入【之前】覆盖为 sqlite:///:memory:，
#      app.database 的模块级 engine 因此绑定内存库，全程不碰开发库 fault_tracker.db；
#   ② 集成走 ASGI：httpx AsyncClient + ASGITransport 直接调 app，不起 uvicorn、不占端口；
#   ③ 依赖覆盖隔离：app.dependency_overrides 把 get_db 换成测试 session，
#      请求链路与测试断言操作同一个内存库会话。
#
# 第三阶段新增：
#   ④ `client` 默认以 admin_user 身份发起请求（get_current_user 覆盖），使旧有 HTTP 测试
#      无需重写即可继续跑；需要真实 JWT 流的（test_api_auth、test_phase3_workflow::TestAuth）
#      改用 `raw_client`；需要以其它角色发起的，通过 `login_as` fixture 现场切换 override。
#
# 为什么环境变量必须在 import app 之前设置？
#   app/config.py 的 settings 是模块级单例（import 时即读 .env 固化），
#   app/database.py 的 engine 同样是模块级创建。导入顺序错了就会绑到开发库。
#   pydantic-settings 的优先级：环境变量 > .env 文件 > 字段默认值（已核实 config.py）。

import os

# ---- ① 环境隔离：必须先于任何 app.* 导入 ----
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["DB_ECHO"] = "false"

from collections.abc import AsyncIterator, Callable, Iterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import database  # noqa: E402
from app.auth import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, FaultRole, User  # noqa: E402


# ---- 测试专用 engine：按方言选择连接参数与连接池 ----
if _TEST_DB_URL.startswith("sqlite"):
    test_engine: Engine = create_engine(
        _TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    test_engine: Engine = create_engine(_TEST_DB_URL)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """每个测试独享干净表结构：先 drop_all 再 create_all，用完再 drop_all。"""
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(test_engine)


# ---- 第三阶段：测试用户工厂 + 默认角色实例 ----
def _mk_user(db: Session, username: str, role: FaultRole, display_name: str | None = None) -> User:
    """直连测试库建用户，跳过 hash 流程（password_hash 只存占位串，测试不用它验证）。"""
    u = User(
        username=username,
        password_hash="$2b$12$placeholder_not_verified_in_tests",
        display_name=display_name or username,
        role=role,
        is_active=True,
        token_version=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def admin_user(db_session: Session) -> User:
    return _mk_user(db_session, "test_admin", FaultRole.admin, "测试管理员")


@pytest.fixture
def handler_user(db_session: Session) -> User:
    return _mk_user(db_session, "test_handler", FaultRole.handler, "测试处理员")


@pytest.fixture
def creator_user(db_session: Session) -> User:
    return _mk_user(db_session, "test_creator", FaultRole.user, "测试报修人")


# ---- 客户端 fixture ----
# raw_client：不覆盖 get_current_user，用于真实 JWT 流（login/logout/me 及权限红测）
# client：默认以 admin 身份注入，旧有 HTTP 测试无需改动即可继续跑
@pytest.fixture
async def raw_client(db_session: Session) -> AsyncIterator[httpx.AsyncClient]:
    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[database.get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def client(
    db_session: Session, admin_user: User
) -> AsyncIterator[httpx.AsyncClient]:
    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[database.get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def login_as(db_session: Session) -> Callable[[User], None]:
    """在 client 已注入 admin 的基础上，把当前请求身份切给指定 user（同 db_session 内的用户）。

    用法：
        def test_xxx(client, login_as, handler_user):
            login_as(handler_user)
            resp = await client.get("/api/faults")   # 以 handler 视角
    """

    def _set(user: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    return _set


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """anyio 的 pytest 插件要求声明后端；本项目 async 测试全部跑 asyncio。"""
    return "asyncio"
