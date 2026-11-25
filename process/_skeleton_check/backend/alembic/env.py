from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import create_engine, pool

from alembic import context

# ── 接入本项目（backend/）的包路径、ORM 基类与配置 ──────────────────────
# 把 backend/ 目录插进 sys.path，保证 app.database / app.config 无论从哪个
# 工作目录运行 alembic 都能导入（alembic.ini 的 prepend_sys_path = . 只覆盖
# "从 backend/ 运行"的情况）。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
# 业务接入：模型定义完成后取消下一行注释，autogenerate 才能看到模型表结构。
# from app import models  # noqa: E402,F401

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


def _database_url() -> str:
    """取与 app 相同的连接串（读 backend/.env，未配置时用默认 SQLite 路径）。"""
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
