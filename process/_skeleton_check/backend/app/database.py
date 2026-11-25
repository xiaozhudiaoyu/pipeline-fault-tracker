# 模块：engine 与 session（SQLAlchemy 2 · SQLite 版）。
#
# SQLite 注意点：
#   · SQLite 是文件数据库，无需 pool_pre_ping / pool_recycle（没有服务端超时断连问题）；
#   · SQLite 默认不支持多线程共享连接，FastAPI 多线程场景需 connect_args={"check_same_thread": False}；
#   · 建表用 Base.metadata.create_all()（允许自动建表方式初始化 SQLite）。
#
# Engine 与 Session 的职责区分：
#   Engine  = 连接池 + 方言，进程级单例，线程安全；
#   Session = 一次工作单元，请求级生命周期，用完即关。
#
# 本模块同时定义 ORM 声明基类 Base（骨架阶段不单设 models.py）：
#   业务模型接入时 `from app.database import Base` 继承即可（见 SKILL.md「业务接入指南」）。

from collections.abc import Iterator

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。

    业务模型（如 app/models.py）继承它并自动注册进 Base.metadata；
    建表（init_models）与迁移（alembic/env.py 的 target_metadata）都读这份 metadata。
    """


# ---- Engine（进程级单例）----
# check_same_thread=False：SQLite 默认只允许创建它的线程使用连接；
#   FastAPI 用线程池跑同步路由，同一个 engine 会被多个线程访问，必须关掉这个检查。
#   安全性由 SQLAlchemy 的连接池保证（每个线程从池里取独立连接）。
engine: Engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args={"check_same_thread": False},
)

# ---- Session 工厂 ----
# expire_on_commit=False：commit 后对象属性不过期，接口里"先 commit 再序列化响应"不会触发额外 SELECT。
# autoflush=False：写入时机由显式 flush/commit 控制，更容易看清哪一步发了 SQL。
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

    create_all 只建【已被 import 的模型】对应的表：业务模型接入后（通常经
    routers → crud → models 的 import 链在应用构建期完成注册），启动时自动建表。

    checkfirst=True（默认值，显式写出强调）：表已存在则跳过，可反复执行不报错。
    但它【不会】修改已存在的表 —— 给模型加了字段再跑一次是没用的，旧表原样不动。
    想同步结构变更，用 Alembic（本模板已引入，见 alembic/ 目录）。

    它同样【不会】删表。删表要显式调用 Base.metadata.drop_all()，
    属破坏性操作，本模块故意不提供封装，避免被顺手调用。
    """
    Base.metadata.create_all(engine, checkfirst=True)


def existing_tables() -> list[str]:
    """返回数据库里当前实际存在的表名列表（反射，不读 Python 模型定义）。

    拿它和 Base.metadata.tables 的键对比，就能发现"模型里有、库里没有"的漂移。
    """
    return list(inspect(engine).get_table_names())
