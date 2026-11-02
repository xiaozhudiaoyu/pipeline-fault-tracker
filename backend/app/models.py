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

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """所有 ORM 模型的共同基类。

    SQLAlchemy 2.0 写法：自定义继承 DeclarativeBase 的类，而非 1.x 的 declarative_base() 函数。
    Base 变成真实类后，Pyright 才能推断子类里 Mapped[int] 对应的实例属性就是 int。
    它身上还挂着 Base.metadata —— 所有表"图纸"的集合，create_all() 据此建表。
    """


class FaultStatus(str, enum.Enum):
    """故障处理状态。

    继承 str 的好处：
      · JSON 序列化时自动变成字符串（"pending"），前端无需额外处理；
      · Pydantic 2 能直接用它做类型标注与校验；
      · SQLAlchemy 的 Enum 列类型会把它映射为 VARCHAR + CHECK 约束（SQLite 上）。

    状态流转规则（后端硬校验，见 crud.py）：
      pending → processing：允许
      pending → done：允许（handling_note 必填）
      processing → done：允许（handling_note 必填）
      processing → pending：允许（回退）
      done → *：禁止（需求："已完成的记录不能直接恢复为待处理"）
    """

    pending = "pending"        # 待处理
    processing = "processing"  # 处理中
    done = "done"              # 已完成


class FaultPriority(str, enum.Enum):
    """故障优先级（第二阶段需求）。

    与 FaultStatus 同为 (str, enum.Enum)：JSON 序列化成字符串、Pydantic 直接做校验、
    SQLAlchemy Enum 列在 SQLite 上渲染成 VARCHAR（无 CHECK 约束，同 status）。

    业务规则（需求二.1）：
      · 新建故障默认 normal（普通）；
      · 详情中可修改，修改优先级【不改变】处理状态 —— 两者是独立维度；
      · 旧库升级时已有故障统一回填 normal（见 alembic 迁移）。
    """

    normal = "normal"  # 普通
    urgent = "urgent"  # 紧急


class Pipeline(Base):
    """流水线主数据表。

    故障必须归属于某条流水线（一对多：Pipeline → PipelineFault）。
    单独建表而非在 fault 里存字符串，是为了：
      · 筛选时按 pipeline_id 关联查询，避免字符串拼写不一致；
      · 将来加流水线属性（负责人、区域）不用改 fault 表。
    """

    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="流水线主键，数据库自增",
    )

    # code 唯一：业务编码（如 "LINE-A"），用于快速识别，不允许重复。
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="流水线编码，全表唯一，如 LINE-A",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="流水线名称，如 总装线A",
    )

    # Text 用于较长描述，SQLite 上 TEXT 无长度限制。
    description: Mapped[str | None] = mapped_column(
        Text,
        comment="流水线描述，选填",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="入库时间，由数据库生成",
    )

    # ---- relationship：一对多的"一"端 ----
    # back_populates="pipeline" 与 PipelineFault.pipeline 互为镜像。
    # cascade="all, delete-orphan"：删流水线时连带删其下所有故障记录，
    #   避免留下 pipeline_id 指向不存在流水线的"孤儿故障"。
    faults: Mapped[list["PipelineFault"]] = relationship(
        back_populates="pipeline",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Pipeline(id={self.id!r}, code={self.code!r}, name={self.name!r})"


class PipelineFault(Base):
    """故障记录表 —— 本项目核心业务实体。

    字段设计依据需求文档"1. 故障登记"：
      所属流水线（pipeline_id）、发生位置（location）、发生时间（occurred_at）、
      故障现象（symptom）为必要信息；具体字段由开发者自行设计，故补充：
      状态（status）、处理说明（handling_note）、完成时间（closed_at）支撑业务闭环。
    """

    __tablename__ = "pipeline_faults"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="故障主键，数据库自增",
    )

    # ---- 外键：一对多的"多"端 ----
    # ondelete="CASCADE"：数据库层行为，删 Pipeline 时自动清掉关联故障。
    #   与 ORM 层 cascade="all, delete-orphan" 双保险（前者防绕过 ORM 的 SQL，后者防 ORM 操作）。
    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属流水线 ID，外键关联 pipelines.id",
    )

    location: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="故障发生位置，如 3号工位传送带",
    )

    # occurred_at 是"故障发生时间"（业务时间），由用户登记时填写；
    # created_at 是"记录入库时间"（系统时间），由数据库生成。两者可能不同（补录场景）。
    # index=True：列表页按它倒序排序 + 时间范围筛选，是查询热点列；
    #   与 Alembic 迁移 a74bf448a946（ix_pipeline_faults_occurred_at）保持一致。
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="故障发生时间（业务时间，用户填写）",
    )

    symptom: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="故障现象描述",
    )

    # ---- 状态 ----
    # Enum(FaultStatus) 在 SQLite 上生成 VARCHAR + CHECK 约束，非法值数据库层直接拒绝。
    # default=FaultStatus.pending：Python 端默认值，新建故障默认为待处理。
    status: Mapped[FaultStatus] = mapped_column(
        Enum(FaultStatus),
        default=FaultStatus.pending,
        nullable=False,
        comment="处理状态：pending/processing/done",
    )

    # ---- 优先级（第二阶段需求）----
    # 与 status 同构：Enum 列 + Python 端 default，普通/紧急两档，登记时不选即 normal。
    # 独立于 status：修改 priority 不影响处理状态（crud.update_fault 只应用传了的字段）。
    priority: Mapped[FaultPriority] = mapped_column(
        Enum(FaultPriority),
        default=FaultPriority.normal,
        nullable=False,
        comment="优先级：normal/urgent，默认普通",
    )

    # handling_note 在状态推进时填写；pending → done 或 processing → done 时必填（crud 层校验）。
    handling_note: Mapped[str | None] = mapped_column(
        Text,
        comment="处理说明，完成时必填",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="记录入库时间，由数据库生成",
    )

    # updated_at：每次 UPDATE 时由数据库自动刷新（onupdate=func.now()）。
    # 注意 onupdate 是 SQLAlchemy 层行为（ORM UPDATE 时触发），非数据库 DDL 的 ON UPDATE；
    # 绕过 ORM 的直接 SQL UPDATE 不会刷新它。本项目所有写操作都走 ORM，足够。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="最后更新时间，ORM UPDATE 时自动刷新",
    )

    # closed_at：状态变为 done 时写入，记录"完成时刻"；未完成时为 NULL。
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        comment="完成时间，状态变为 done 时写入",
    )

    # ---- relationship：一对多的"多"端导航 ----
    # fault.pipeline 让你从故障对象直接跳到所属流水线，底层生成 SELECT ... WHERE id = ?。
    pipeline: Mapped["Pipeline"] = relationship(
        back_populates="faults",
    )

    def __repr__(self) -> str:
        return (
            f"PipelineFault(id={self.id!r}, pipeline_id={self.pipeline_id!r}, "
            f"status={self.status!r}, occurred_at={self.occurred_at!r})"
        )
