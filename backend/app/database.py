# 模块：engine 与 session（SQLAlchemy 2 · 多方言：SQLite 开发库 / PostgreSQL 容器库）。
#
# 方言由 settings.database_url 的 scheme 决定，本模块据此选择连接参数：
#   · SQLite（本地开发默认）：文件数据库，无需 pool_pre_ping / pool_recycle（没有服务端超时断连问题）；
#     默认不支持多线程共享连接，FastAPI 多线程场景需 connect_args={"check_same_thread": False}。
#   · PostgreSQL（compose 注入 postgresql+psycopg://...）：服务端数据库，psycopg 驱动
#     【不接受】check_same_thread 参数（SQLite 专属），故按方言分支，仅在 SQLite 时传它。
#   · 建表统一用 Base.metadata.create_all()（迁移路径 a：保守，Alembic 仅作练习产物）。
#
# Engine 与 Session 的职责区分（同 day15_orm）：
#   Engine  = 连接池 + 方言，进程级单例，线程安全；
#   Session = 一次工作单元，请求级生命周期，用完即关。

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base


def ensure_sqlite_dir(url: str) -> None:
    """SQLite 文件库的父目录不存在时自动创建（需求五.4）。

    原缺陷：把 DATABASE_URL 改成 `sqlite:///./data/fault_tracker.db` 这类带子目录的路径后，
    新解压的项目里没有 `backend/data/`，首次连库直接 `sqlite3.OperationalError:
    unable to open database file`（建 engine 本身不报错，它懒连；错在真正 connect 时）。
    本函数在建 engine / 跑迁移前先把父目录 mkdir(parents=True)，README 无需再加手工建目录步骤。

    两种无需建目录的情形提前返回：非 SQLite（PG 没有“库文件路径”概念，其
    database 段是库名，拿去 mkdir 会凭空造出一个目录）；内存库 `:memory:` / 无路径 `sqlite://`。
    """
    if not url.startswith("sqlite"):
        return
    db_path = make_url(url).database
    if not db_path or db_path == ":memory:":
        return
    Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


# ---- Engine（进程级单例）----
# 按方言分支连接参数：
#   SQLite 需 check_same_thread=False —— 它默认只允许创建连接的线程使用该连接；
#     FastAPI 用线程池跑同步路由，同一个 engine 会被多个线程访问，必须关掉这个检查。
#     安全性由 SQLAlchemy 的连接池保证（每个线程从池里取独立连接）。
#   PostgreSQL（psycopg）不认这个参数，传进去会 TypeError，故仅 SQLite 时传。
_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# 建 engine 前保证库文件父目录存在（alembic/env.py 自己建 engine，那里也调了同一函数）。
if _is_sqlite:
    ensure_sqlite_dir(settings.database_url)

engine: Engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args=_connect_args,
)

# ---- SQLite 外键约束开启（第三阶段新增）----
# SQLite 默认 PRAGMA foreign_keys=OFF，建表时声明的 ON DELETE CASCADE/SET NULL
# 不会在数据库层强制执行（PG 默认强制）。本项目第三阶段引入 User 外键后，
# 需要保证删除/停用用户时 SET NULL 等约束生效，故每个连接建立时开启。
# 用 event.listens_for 而非 connect_args 里的 pragma 参数：后者只在 create_engine
# 层设置一次，连接池回收复用后可能失效；event 保证每次新连接都执行。
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ---- Session 工厂 ----
# expire_on_commit=False：commit 后对象属性不过期，接口里"先 commit 再序列化响应"不会触发额外 SELECT。
# autoflush=False：写入时机由显式 flush/commit 控制，学习阶段更容易看清哪一步发了 SQL。
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每个请求发放一个 Session，请求结束自动关闭。

    用法（路由里）：
        db: Session = Depends(get_db)

    yield 之前的代码 = 请求开始时执行（发放 session）；
    yield 之后的代码 = 请求结束时执行（关闭 session，无论成功或异常）。
    注意：这里【不】自动 commit —— 提交时机由业务代码（crud 层）显式控制，
    避免"路由还没处理完就提前提交"的时序问题。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_models() -> None:
    """建表：把 Base.metadata 里的全部"图纸"翻译成 CREATE TABLE 并执行。

    checkfirst=True（默认值，显式写出强调）：表已存在则跳过，可反复执行不报错。
    但它【不会】修改已存在的表 —— 给模型加了字段再跑一次是没用的，旧表原样不动。
    想同步结构变更，要么手工 ALTER，要么用 Alembic（本项目未引入，需求未要求）。

    它同样【不会】删表。删表要显式调用 Base.metadata.drop_all()，
    属破坏性操作，本模块故意不提供封装，避免被顺手调用。
    """
    Base.metadata.create_all(engine, checkfirst=True)


def existing_tables() -> list[str]:
    """返回数据库里当前实际存在的表名列表（反射，不读 Python 模型定义）。

    拿它和 Base.metadata.tables 的键对比，就能发现"模型里有、库里没有"的漂移。
    """
    return list(inspect(engine).get_table_names())
