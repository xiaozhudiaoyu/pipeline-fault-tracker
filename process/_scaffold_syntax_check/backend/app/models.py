# 模块：ORM 模型（SQLAlchemy 2 声明式映射）。
#
# 一个类 = 一张表，一个实例 = 一行记录，一个类属性 = 一个字段。
# 与 schemas.py 里的 Pydantic 模型职责不同：
#   Pydantic BaseModel —— 管"HTTP 接口收什么、发什么"，活在接口边界；
#   SQLAlchemy Base    —— 管"数据库里存什么"，活在持久层。
#
# 本项目用 SQLite，无需 MySQL 专用的 __table_args__（engine/charset）。

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的共同基类。

    SQLAlchemy 2.0 写法：自定义继承 DeclarativeBase 的类，而非 1.x 的 declarative_base() 函数。
    Base 变成真实类后，类型检查器才能推断子类里 Mapped[int] 对应的实例属性就是 int。
    它身上还挂着 Base.metadata —— 所有表"图纸"的集合，create_all() 据此建表。
    """


class ItemStatus(str, enum.Enum):
    """演示用状态枚举。业务实体照此模式定义自己的枚举。

    继承 str 的好处：
      · JSON 序列化时自动变成字符串（"active"），前端无需额外处理；
      · Pydantic 2 能直接用它做类型标注与校验；
      · SQLAlchemy 的 Enum 列类型会把它映射为 VARCHAR。
    """

    active = "active"        # 启用中
    archived = "archived"    # 已归档


class Item(Base):
    """示例实体 —— 演示标准字段组合（主键 / 唯一 / 枚举 / 可选 / 时间戳）。

    新项目按业务把本类替换为真实实体；字段设计照此模式：
      · id 主键自增；
      · 业务唯一字段加 unique=True（写入前在 crud 层查重，抛 409 而非依赖 IntegrityError）；
      · 状态类字段用 str 枚举；
      · created_at / updated_at 由数据库生成，业务时间（若有）单独建列。
    """

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="主键，数据库自增",
    )

    # name 唯一：业务编码/名称，不允许重复（crud 层先查重 → 409）。
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="名称，全表唯一",
    )

    # Text 用于较长描述，SQLite 上 TEXT 无长度限制。
    description: Mapped[str | None] = mapped_column(
        Text,
        comment="描述，选填",
    )

    # Enum(ItemStatus) 在 SQLite 上生成 VARCHAR；default 是 Python 端默认值，不进 DDL。
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus),
        default=ItemStatus.active,
        nullable=False,
        comment="状态：active/archived",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="入库时间，由数据库生成",
    )

    # updated_at：每次 UPDATE 时由数据库自动刷新（onupdate=func.now()）。
    # 注意 onupdate 是 SQLAlchemy 层行为（ORM UPDATE 时触发），非数据库 DDL 的 ON UPDATE；
    # 绕过 ORM 的直接 SQL UPDATE 不会刷新它。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="最后更新时间，ORM UPDATE 时自动刷新",
    )

    def __repr__(self) -> str:
        return f"Item(id={self.id!r}, name={self.name!r}, status={self.status!r})"
