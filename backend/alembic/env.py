from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import create_engine, pool

from alembic import context

# ── 接入本项目（backend/）的包路径、ORM 模型与配置 ──────────────────────
# 把 backend/ 目录插进 sys.path，保证 app.models / app.config 无论从哪个
# 工作目录运行 alembic 都能导入（alembic.ini 的 prepend_sys_path = . 只覆盖
# "从 backend/ 运行"的情况）。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.database import ensure_sqlite_dir  # noqa: E402
from app.models import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 靠对比两份 schema 工作：一份 target_metadata（Python 模型里的
# 目标结构），一份数据库里的现状（反射读出）。所以必须把 Base.metadata 交给它，
# 否则 target_metadata=None，autogenerate 什么都对比不出来。
target_metadata = Base.metadata

# 连接串与 app 同源：database.py 建 engine 用 settings.database_url，这里也一样；
# alembic.ini 里的 sqlalchemy.url 只是占位符，真实值以 app.config 为准，
# 避免连接信息在两处维护出现漂移。注意默认值 "sqlite:///./fault_tracker.db"
# 相对当前工作目录解析，故迁移命令统一在 backend/ 下执行（见 README「数据库迁移」）。
# 离线模式（--sql）也走同一 URL，保证生成的 SQL 与在线执行一致。


def _database_url() -> str:
    """取与 app 相同的连接串（读 backend/.env，未配置时用默认 SQLite 路径）。

    顺便保证库文件父目录存在（需求五.4）：迁移进程不经过 app.database 的建 engine 路径
    （本文件自己 create_engine / 离线模式只给 URL），所以那边新增的自动建目录在这里
    也得调一次；否则 DATABASE_URL 指向 `./data/` 等不存在的子目录时，
    `alembic upgrade head` 会报 unable to open database file。
    """
    ensure_sqlite_dir(settings.database_url)
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # SQLite 没有服务端连接池概念，NullPool 每用即建、用完即放，
    # 适合迁移这种一次性短事务场景。
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
