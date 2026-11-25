# SQLAlchemy 2.0 完整用法速查

> 基于 SQLAlchemy 2.0.52（本项目锁定版本，见 [requirements.txt](./requirements.txt)），从入门到能干活。所有 API 均为 2.0 稳定接口。
>
> 1.x 老写法（`session.query()`、`declarative_base()`、`Column()` 主导）作为对比会标出来，遇到旧教程直接跳过老写法。
>
> 本文档由 Qoder 会话整理落盘，作为项目内 SQLAlchemy 用法的通用参考；附录部分给出本仓库的实证落地。

---

## 一、SQLAlchemy 的分层

```
┌──────────────────────────────────────┐
│  ORM 层（sqlalchemy.orm）            │  ← 类 ↔ 表；对象 ↔ 行；session
├──────────────────────────────────────┤
│  Core 层（sqlalchemy）               │  ← 表达式语言：select/insert/update/delete
│    · Table / Column / MetaData       │     面向"表"和"SQL 语句"
│    · Engine / Connection             │
├──────────────────────────────────────┤
│  DBAPI（PyMySQL / psycopg / sqlite3） │  ← 驱动
└──────────────────────────────────────┘
```

**关键认知**：ORM 是 Core 之上的一层封装。你完全可以只用 Core（写 SQL 表达式但不映射类），也可以只用 ORM。生产项目里通常混用——ORM 定义模型，Core 表达式写复杂查询。

### 三大组件

| 组件 | 职责 | 典型用法 |
|---|---|---|
| **Engine** | 连接池 + 方言适配，全局唯一 | `create_engine(url)` |
| **Connection** | 一次数据库连接，执行 SQL | `with engine.connect() as conn:` |
| **Session** | ORM 的工作单元，管理对象状态 | `with Session(engine) as session:` |

---

## 二、安装与生态

```bash
pip install SQLAlchemy             # 核心，无默认驱动
pip install SQLAlchemy[asyncio]    # 异步支持（greenlet）
pip install PyMySQL                # MySQL 驱动（纯 Python）
pip install mysqlclient            # MySQL 驱动（C 扩展，更快）
pip install psycopg[binary]        # PostgreSQL 驱动（3.x）
pip install asyncpg                # PostgreSQL 异步驱动
pip install aiosqlite              # SQLite 异步驱动
```

### 方言 + 驱动 URL 格式

`<dialect>+<driver>://<user>:<pass>@<host>:<port>/<db>?<query>`

| 数据库 | URL |
|---|---|
| SQLite（文件） | `sqlite:///./app.db` |
| SQLite（内存） | `sqlite:///:memory:` 或 `sqlite://` |
| MySQL (PyMySQL) | `mysql+pymysql://user:pass@localhost:3306/db?charset=utf8mb4` |
| MySQL (mysqlclient) | `mysql+mysqldb://user:pass@localhost/db` |
| MySQL (asyncmy) | `mysql+asyncmy://user:pass@localhost/db` |
| PostgreSQL (psycopg2) | `postgresql+psycopg2://user:pass@localhost/db` |
| PostgreSQL (psycopg3) | `postgresql+psycopg://user:pass@localhost/db` |
| PostgreSQL (asyncpg) | `postgresql+asyncpg://user:pass@localhost/db` |
| MSSQL | `mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server` |
| Oracle | `oracle+oracledb://user:pass@host/db` |
| MariaDB | `mariadb+pymysql://user:pass@localhost/db` |

**安全要点**：URL 里含密码，不要硬编码进 Git。用环境变量或配置文件（本项目用 [day15_orm/db_config_local.py](./day15_orm/db_config_local.py)，被 `.gitignore` 排除）。

---

## 三、Engine 与连接池

### 3.1 创建 Engine

```python
from sqlalchemy import create_engine

engine = create_engine(
    url,
    echo=False,              # True 时把每条 SQL 打到日志，调试用
    echo_pool=False,         # True 时打印连接池事件
    pool_size=5,             # 连接池常驻连接数（默认 5）
    max_overflow=10,         # 允许超过 pool_size 的临时连接数（默认 10）
    pool_timeout=30,         # 拿不到连接时最多等多少秒
    pool_recycle=3600,       # 连接存活多久后回收（MySQL 8h 超时必须配）
    pool_pre_ping=True,      # 用连接前先 ping 一下，避免拿到断开的死连接
    isolation_level=None,    # 事务隔离级别（None = 用数据库默认）
    future=True,             # 2.0 里已默认，写不写都行
)

engine.dispose()             # 关闭所有连接（应用退出时调）
```

### 3.2 连接池类型

| 池类型 | 行为 | 场景 |
|---|---|---|
| `QueuePool`（默认） | 常驻 N 个连接，用完归还 | 生产用 |
| `NullPool` | 不池化，每次开新连接 | Alembic 迁移用这个 |
| `SingletonThreadPool` | 单线程共享一个连接 | SQLite 内存库测试用 |
| `StaticPool` | 全局一个连接 | SQLite `:memory:` 必须用 |
| `AsyncAdaptedQueuePool` | 异步版 QueuePool | 异步模式自动用 |

```python
from sqlalchemy.pool import StaticPool, NullPool

# SQLite 内存库必须用 StaticPool，否则每个连接是独立的内存库
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Alembic 迁移用 NullPool
engine = create_engine(url, poolclass=NullPool)
```

### 3.3 Engine 的生命周期

- **全局唯一**：一个应用一个 Engine（或每个数据库一个）。
- **线程安全**：Engine 本身线程安全，Connection 不是。
- **不要每次请求都 create_engine**：连接池就废了。
- **应用退出时 `engine.dispose()`**：释放所有连接。

---

## 四、Core 层：不用 ORM 也能写 SQL

### 4.1 定义表

```python
from sqlalchemy import MetaData, Table, Column, Integer, String, ForeignKey, DateTime, func

metadata = MetaData()

users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(50), nullable=False, unique=True),
    Column("email", String(120)),
    Column("created_at", DateTime, server_default=func.now()),
)

todos = Table(
    "todos", metadata,
    Column("id", Integer, primary_key=True),
    Column("content", String(200), nullable=False),
    Column("owner_id", ForeignKey("users.id", ondelete="CASCADE")),
)

metadata.create_all(engine)   # 建表（幂等，已存在则跳过）
metadata.drop_all(engine)     # 删表
```

### 4.2 表达式语言：select / insert / update / delete

```python
from sqlalchemy import select, insert, update, delete, and_, or_, func, text

# SELECT
stmt = select(users).where(users.c.name == "alice")
stmt = select(users.c.id, users.c.name).where(and_(users.c.id > 1, users.c.name.like("a%")))
stmt = select(users).order_by(users.c.id.desc()).limit(10).offset(20)
stmt = select(func.count()).select_from(users).where(users.c.email.is_not(None))
stmt = select(users).join(todos, users.c.id == todos.c.owner_id).where(todos.c.content.like("%x%"))

# INSERT
stmt = insert(users).values(name="alice", email="a@x.com")
stmt = insert(users).values([{"name": "a"}, {"name": "b"}])       # 批量

# UPDATE
stmt = update(users).where(users.c.id == 1).values(email="new@x.com")
stmt = update(users).where(users.c.id == 1).values({users.c.name: users.c.name + "_x"})

# DELETE
stmt = delete(users).where(users.c.id == 1)

# 执行
with engine.connect() as conn:
    result = conn.execute(stmt)
    conn.commit()          # 或 with engine.begin() as conn: 自动 commit
```

### 4.3 结果的四种形态

```python
result = conn.execute(select(users))

result.all()             # list[Row] —— Row 是元组 + 字典的混合体
result.first()           # 第一行 Row 或 None
result.one()             # 必须恰好一行，否则抛异常
result.one_or_none()     # 0 或 1 行

result.fetchall()        # 同 all()
result.mappings().all()  # list[RowMapping] —— 每行是字典 {'id': 1, 'name': 'alice'}
result.scalars().all()   # list[int] —— 只取第一列（ORM 里最常用）
result.scalar()          # 第一行第一列的单个值
result.scalar_one()      # 必须恰好一行一列
```

**Row 的访问方式**：

```python
row = result.first()
row[0]                   # 按索引
row["id"]                # 按列名
row.id                   # 按属性（推荐）
tuple(row)               # 转元组
dict(row._mapping)       # 转字典
```

### 4.4 原生 SQL 逃生口

```python
from sqlalchemy import text

with engine.begin() as conn:
    rows = conn.execute(text("SELECT * FROM users WHERE id = :uid"), {"uid": 1}).all()
    conn.execute(text("UPDATE users SET name = :n WHERE id = :i"), {"n": "x", "i": 1})
```

**永远用 `:name` 绑定参数，不要字符串拼接**（SQL 注入）。

### 4.5 事务边界

```python
# 手动事务
with engine.connect() as conn:
    conn.execute(...)
    conn.commit()          # 必须显式 commit

# 自动事务（推荐）
with engine.begin() as conn:
    conn.execute(...)
    conn.execute(...)
    # 退出时自动 commit；异常时自动 rollback

# 嵌套事务（SAVEPOINT）
with engine.begin() as conn:
    conn.execute(...)
    try:
        with conn.begin_nested():
            conn.execute(...)   # 失败只回滚到这里
    except Exception:
        pass                     # 外层事务不受影响
```

---

## 五、ORM 层：2.0 声明式映射

### 5.1 定义模型

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(120))         # 可空
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # 一对多："一"端
    todos: Mapped[list["Todo"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r})"

class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(String(200))
    done: Mapped[bool] = mapped_column(default=False)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # 一对多："多"端
    owner: Mapped[Optional["User"]] = relationship(back_populates="todos")

Base.metadata.create_all(engine)
```

### 5.2 2.0 vs 1.x 对照

| 1.x | 2.0 |
|---|---|
| `Base = declarative_base()` | `class Base(DeclarativeBase): pass` |
| `id = Column(Integer, primary_key=True)` | `id: Mapped[int] = mapped_column(primary_key=True)` |
| `todos = relationship("Todo", backref="owner")` | `todos: Mapped[list["Todo"]] = relationship(back_populates="owner")` |
| `session.query(User).filter_by(...)` | `session.scalars(select(User).where(...))` |
| `session.query(User).get(1)` | `session.get(User, 1)` |
| `session.query(User).first()` | `session.scalars(select(User)).first()` |
| `session.query(User).count()` | `session.scalar(select(func.count()).select_from(User))` |

### 5.3 `Mapped[T]` 类型规则

| 写法 | 数据库层 |
|---|---|
| `Mapped[int]` | NOT NULL |
| `Mapped[Optional[int]]` / `Mapped[int \| None]` | NULL |
| `Mapped[str]` | NOT NULL + VARCHAR（长度必须显式给） |
| `Mapped[list["Todo"]]` | 一对多的"多"端（`relationship`） |
| `Mapped["User"]` | 一对一 / 多对一（`relationship`） |
| `Mapped[datetime]` | DATETIME / TIMESTAMP |
| `Mapped[bool]` | BOOLEAN / TINYINT |
| `Mapped[Decimal]` | NUMERIC |
| `Mapped[dict]` | JSON（需要方言支持） |

**前向引用**：类还没定义完时，用字符串 `"Todo"`。可空的联合类型必须整体加引号：`Mapped["User | None"]`（Python 3.14 上单独给 `None` 加引号会报错）。

### 5.4 `mapped_column()` 的常用参数

```python
mapped_column(
    # 类型（不给就从 Mapped[T] 推断）
    String(50),

    # 约束
    primary_key=True,
    autoincrement=True,
    nullable=False,             # 也可以从 Mapped[Optional[...]] 自动推断
    unique=True,
    index=True,                 # 建单列索引
    default=False,              # Python 端默认值（ORM 层填充）
    server_default=func.now(),  # 数据库端默认值（DDL 里的 DEFAULT）
    server_onupdate=func.now(), # 更新时数据库端自动填（需要触发器支持）
    onupdate=func.now(),        # Python 端更新时自动填
    comment="字段说明",          # 写进 DDL 的 COMMENT
    doc="Python 文档",           # 只出现在 Python 端
    key="python_attr_name",     # Python 属性名和列名不同时用

    # ForeignKey
    ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
)
```

**`default` vs `server_default`**：

| 参数 | 填值方 | DDL 可见 | 绕过 ORM 插入 |
|---|---|---|---|
| `default=` | Python 端 | 否 | 无默认值 |
| `server_default=` | 数据库端 | 是（`DEFAULT ...`） | 有默认值 |

**生产推荐 `server_default`**：任何客户端插入都有值。

### 5.5 关系（relationship）

```python
# 一对多（"一"端）
todos: Mapped[list["Todo"]] = relationship(
    back_populates="owner",        # 反向属性名（推荐，比 backref 显式）
    cascade="all, delete-orphan",  # 级联策略
    lazy="select",                 # 加载策略（下面详述）
    order_by="Todo.created_at",    # 集合默认排序
    uselist=True,                  # False = 一对一
    secondary=None,                # 多对多的中间表
    primaryjoin=None,              # 自定义连接条件（罕用）
    foreign_keys=None,             # 多个 FK 时指定用哪个
    viewonly=False,                # True = 只读关系，不写回数据库
)

# 多对多
todo_tags = Table(
    "todo_tags", Base.metadata,
    Column("todo_id", ForeignKey("todos.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",  ForeignKey("tags.id",  ondelete="CASCADE"), primary_key=True),
)

class Todo(Base):
    tags: Mapped[list["Tag"]] = relationship(secondary=todo_tags, back_populates="todos")

class Tag(Base):
    todos: Mapped[list["Todo"]] = relationship(secondary=todo_tags, back_populates="tags")
```

### 5.6 `cascade` 常用值

| 值 | 行为 |
|---|---|
| `"all, delete-orphan"` | 父删子跟着删，从集合移除也删（一对多最常用） |
| `"save-update, merge"` | 默认值，父保存子跟着保存 |
| `"delete"` | 只删父时删子，从集合移除不删 |
| `"refresh-expire"` | 父刷新/过期时子也跟着 |
| `"expunge"` | 父被 expunge 时子也跟着 |

### 5.7 加载策略（`lazy=`）

| 值 | 行为 | 场景 |
|---|---|---|
| `"select"`（默认） | 访问时才发第二条 SELECT | 简单场景，但循环里访问 = N+1 |
| `"joined"` | 用 JOIN 一次拉回 | 一对一 / 多对一，或小集合 |
| `"selectin"` | 用第二条 `SELECT ... WHERE id IN (...)` 一次拉回 | 一对多集合的推荐 |
| `"subquery"` | 类似 selectin，用子查询 | 老版本兼容 |
| `"raise"` | 访问就抛错 | 强制显式预加载 |
| `"noload"` | 永远返回空 | 罕用 |
| `"write_only"` | 只写不读（2.0 新） | 大集合，只 append 不遍历 |
| `"dynamic"` | 返回 Query 对象（1.x 遗留） | 2.0 不推荐 |

**查询时动态覆盖**：

```python
from sqlalchemy.orm import selectinload, joinedload, lazyload, raiseload

stmt = select(User).options(selectinload(User.todos))           # 推荐
stmt = select(User).options(joinedload(User.todos))
stmt = select(Todo).options(selectinload(Todo.tags).selectinload(Tag.owner))  # 嵌套
stmt = select(User).options(raiseload(User.todos))              # 强制不加载，访问就报错
```

---

## 六、Session：ORM 的工作单元

### 6.1 基本用法

```python
from sqlalchemy.orm import Session, sessionmaker

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

session = SessionLocal()
try:
    user = User(name="alice")
    session.add(user)
    session.commit()
finally:
    session.close()
```

**或用上下文管理器**：

```python
with SessionLocal() as session:
    session.add(user)
    session.commit()
```

**推荐封装 `session_scope`**（自动 commit / rollback / close）：

```python
from contextlib import contextmanager

@contextmanager
def session_scope(engine):
    session = Session(engine)
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
```

### 6.2 Session 的关键参数

```python
Session(
    bind=engine,
    autoflush=False,        # True 时每次查询前自动 flush（默认 True，但推荐显式 False）
    autocommit=False,       # 2.0 里已经强制 False
    expire_on_commit=False, # commit 后是否让所有对象过期（默认 True，会导致再次访问属性时重发 SELECT）
    future=True,            # 2.0 默认
    info={},                # 自定义元数据（可放 request_id 等）
)
```

### 6.3 Session 的核心方法

```python
# 增
session.add(obj)
session.add_all([obj1, obj2])

# 查（2.0 风格，全部基于 select）
session.get(User, 1)                        # 按主键查，先查 identity map 再查库
session.get(User, 1, with_for_update=True)  # SELECT ... FOR UPDATE 加行锁
session.execute(select(User).where(...))    # 通用
session.scalars(select(User).where(...)).all()  # 直接拿 ORM 对象列表
session.scalar(select(func.count()).select_from(User))  # 单值

# 改（对象在 session 里，改属性即可，flush/commit 时自动生成 UPDATE）
user.name = "bob"
session.flush()                             # 把变更发到数据库但不 commit

# 删
session.delete(obj)

# 批量（性能高，绕过 identity map 和 ORM 事件）
session.bulk_insert_mappings(User, [{"name": "a"}, {"name": "b"}])
session.bulk_update_mappings(User, [{"id": 1, "name": "x"}])
session.bulk_save_objects([u1, u2])

# 事务
session.commit()
session.rollback()
session.flush()
session.refresh(obj)                        # 从库重新加载
session.expire(obj)                         # 标记为过期，下次访问时重加载
session.expunge(obj)                        # 从 session 移出（变成 detached）
session.merge(obj)                          # 把 detached 对象合并回 session
```

### 6.4 对象的四种状态

| 状态 | 说明 |
|---|---|
| **transient** | 刚 `new` 出来，还没 `session.add()` |
| **pending** | `add()` 之后、`flush()` 之前 |
| **persistent** | 已入库，在 session 里 |
| **detached** | session 关闭后，或用 `expunge` 移出 |

**detached 对象再访问懒加载属性会抛 `DetachedInstanceError`**——这是最常见的坑之一。解决：`expire_on_commit=False` + 在 session 关闭前把需要的关系预加载好。

### 6.5 Identity Map（身份映射）

Session 内部维护一个"主键 → 对象"的字典。同一个主键在同一个 session 里永远返回同一个 Python 对象：

```python
u1 = session.get(User, 1)
u2 = session.get(User, 1)
assert u1 is u2          # 同一个对象
```

**好处**：避免重复查询，保证对象一致性。
**坑**：跨 session 传递对象会 detached，用 `session.merge(obj)` 合并回来。

---

## 七、查询完整姿势（2.0 风格）

### 7.1 WHERE 条件

```python
from sqlalchemy import select, func, and_, or_, not_, case, distinct, exists

select(User).where(User.name == "alice")
select(User).where(User.name.in_(["alice", "bob"]))
select(User).where(User.name.like("%ali%"))         # LIKE
select(User).where(User.name.ilike("%ALI%"))        # 不区分大小写（PG 有效，MySQL 需要 collation）
select(User).where(User.age.between(18, 60))
select(User).where(User.email.is_(None))
select(User).where(User.email.is_not(None))
select(User).where(and_(User.age > 18, User.name != ""))
select(User).where(or_(User.name == "a", User.name == "b"))
select(User).where(not_(User.name == "a"))
```

### 7.2 排序 / 分页

```python
select(User).order_by(User.created_at.desc(), User.id.asc()).limit(10).offset(20)
```

### 7.3 聚合

```python
select(func.count()).select_from(User)
select(func.count(User.id))
select(func.sum(Todo.done.cast(Integer)))
select(func.avg(User.age))
select(func.max(User.age), func.min(User.age))
```

### 7.4 GROUP BY / HAVING

```python
select(User.name, func.count(Todo.id))\
    .join(Todo, Todo.owner_id == User.id)\
    .group_by(User.name)\
    .having(func.count(Todo.id) > 5)
```

### 7.5 JOIN

```python
select(User, Todo).join(Todo, Todo.owner_id == User.id)             # inner join
select(User, Todo).outerjoin(Todo, Todo.owner_id == User.id)        # left join
select(User).join(Todo).where(Todo.done == True)                    # 有 FK 时可省略 on
```

### 7.6 子查询

```python
subq = select(Todo.owner_id).where(Todo.done == True).scalar_subquery()
select(User).where(User.id.in_(subq))
```

### 7.7 EXISTS

```python
select(User).where(exists(select(Todo.id).where(Todo.owner_id == User.id)))
```

### 7.8 CASE WHEN

```python
select(User.name, case(
    (User.age < 18, "minor"),
    (User.age < 60, "adult"),
    else_="senior",
))
```

### 7.9 DISTINCT

```python
select(distinct(User.name))
```

### 7.10 别名（自连接必备）

```python
from sqlalchemy.orm import aliased

Employee = aliased(User)
Manager = aliased(User)
select(Employee, Manager).join(Manager, Employee.manager_id == Manager.id)
```

### 7.11 只取部分列

```python
# 返回 Row，不是 ORM 对象
select(User.id, User.name).where(...)

# 返回字典
session.execute(select(User.id, User.name)).mappings().all()
```

### 7.12 UPSERT（方言专属）

```python
# MySQL
from sqlalchemy.dialects.mysql import insert as mysql_insert
stmt = mysql_insert(User).values(id=1, name="x")
stmt = stmt.on_duplicate_key_update(name=stmt.inserted.name)

# PostgreSQL
from sqlalchemy.dialects.postgresql import insert as pg_insert
stmt = pg_insert(User).values(id=1, name="x")
stmt = stmt.on_conflict_do_update(index_elements=["id"], set_={"name": "x"})
stmt = pg_insert(User).on_conflict_do_nothing(index_elements=["id"])

# SQLite
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
stmt = sqlite_insert(User).values(id=1, name="x")
stmt = stmt.on_conflict_do_update(index_elements=["id"], set_={"name": "x"})
```

---

## 八、事务与并发

### 8.1 事务边界

```python
# 单事务
with engine.begin() as conn:            # 自动 commit / rollback
    conn.execute(...)
    conn.execute(...)

# 嵌套事务（保存点，SAVEPOINT）
with engine.begin() as conn:
    conn.execute(...)
    try:
        with conn.begin_nested():        # SAVEPOINT
            conn.execute(...)            # 失败只回滚到这里
    except Exception:
        pass                              # 外层事务不受影响
```

### 8.2 隔离级别

```python
engine = create_engine(url, isolation_level="SERIALIZABLE")
# 可选：READ UNCOMMITTED / READ COMMITTED / REPEATABLE READ / SERIALIZABLE
```

### 8.3 悲观锁 vs 乐观锁

```python
# 悲观锁：SELECT ... FOR UPDATE
user = session.get(User, 1, with_for_update=True)

# 乐观锁：version_id_col
class User(Base):
    __mapper_args__ = {"version_id_col": version}
    version: Mapped[int] = mapped_column(default=1)
# 更新时 SQLAlchemy 自动加 WHERE version = :old，冲突抛 StaleDataError
```

### 8.4 事务传播

Session 默认是"一个 session = 一个事务"。嵌套事务用 `begin_nested()`（SAVEPOINT）。

```python
with session.begin():                    # 外层事务
    session.add(u1)
    try:
        with session.begin_nested():     # SAVEPOINT
            session.add(u2)
            raise Exception("boom")
    except:
        pass                              # u2 回滚，u1 保留
```

---

## 九、类型系统

### 9.1 通用类型（跨数据库）

```python
from sqlalchemy import (
    Integer, BigInteger, SmallInteger,
    String, Text, Unicode, UnicodeText,
    Numeric, Float,
    Boolean,
    Date, Time, DateTime, TIMESTAMP, Interval,
    LargeBinary, Enum, JSON,
)

Column("price", Numeric(10, 2))          # 精确小数（金额必用）
Column("data", JSON)                     # 自动序列化 dict/list
Column("status", Enum("active", "inactive", name="status_enum"))
Column("created", DateTime(timezone=True))
Column("duration", Interval)             # timedelta
Column("blob", LargeBinary)
```

### 9.2 方言专属类型

```python
from sqlalchemy.dialects.mysql import TINYINT, MEDIUMTEXT, LONGTEXT, JSON as MYSQL_JSON
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID, INET, CITEXT
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON

Column("data", JSONB)                    # PG 专属，支持索引
Column("tags", ARRAY(String))            # PG 数组
Column("uid", UUID(as_uuid=True))        # PG UUID
Column("ip", INET)                       # PG IP 地址
```

### 9.3 自定义类型（TypeDecorator）

```python
from sqlalchemy.types import TypeDecorator, CHAR
import uuid

class GUID(TypeDecorator):
    """平台无关的 UUID：PG 用原生 UUID，其他数据库用 CHAR(36)。"""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None: return value
        if dialect.name == "postgresql": return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None: return value
        if not isinstance(value, uuid.UUID): return uuid.UUID(value)
        return value
```

---

## 十、事件系统

```python
from sqlalchemy import event
from sqlalchemy.orm import Session

@event.listens_for(engine, "before_cursor_execute")
def log_sql(conn, cursor, statement, parameters, context, executemany):
    logger.debug("SQL: %s | params: %s", statement, parameters)

@event.listens_for(Session, "before_flush")
def audit_changes(session, flush_context, instances):
    for obj in session.new:    ...   # 新增
    for obj in session.dirty:  ...   # 修改
    for obj in session.deleted:...   # 删除

@event.listens_for(User.name, "set")
def on_name_change(target, value, oldvalue, initiator):
    if value != oldvalue:
        logger.info("name changed: %s → %s", oldvalue, value)
```

**常用事件**：

| 事件 | 触发时机 |
|---|---|
| `before_cursor_execute` | 每条 SQL 执行前 |
| `after_cursor_execute` | 每条 SQL 执行后 |
| `before_flush` | session.flush() 前 |
| `after_flush` | session.flush() 后 |
| `before_commit` | session.commit() 前 |
| `after_commit` | session.commit() 后 |
| `set` | 属性赋值时 |
| `init` | 对象 __init__ 时 |
| `load` | 对象从库加载时 |

---

## 十一、高级特性

### 11.1 `hybrid_property`（Python 端和 SQL 端都能用）

```python
from sqlalchemy.ext.hybrid import hybrid_property

class User(Base):
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))

    @hybrid_property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @full_name.expression
    def full_name(cls):
        return func.concat(cls.first_name, " ", cls.last_name)

# Python 端
print(user.full_name)
# SQL 端
select(User).where(User.full_name.like("%alice%"))
```

### 11.2 `association_proxy`（多对多的语法糖）

```python
from sqlalchemy.ext.associationproxy import association_proxy

class Todo(Base):
    tags: Mapped[list["Tag"]] = relationship(secondary=todo_tags, back_populates="todos")
    tag_names = association_proxy("tags", "name")    # 直接拿名字列表

todo.tag_names                       # ["orm", "python"]
todo.tag_names.append("new")         # 自动创建 Tag 并关联（需要 creator）
```

### 11.3 `composite`（多列组成一个值对象）

```python
from sqlalchemy.orm import composite

class Point:
    def __init__(self, x, y): self.x, self.y = x, y

class Vertex(Base):
    x1: Mapped[int]
    y1: Mapped[int]
    start = composite(Point, x1, y1)

v.start.x    # Python 端当对象用
```

### 11.4 继承映射

```python
# 单表继承（推荐，性能好）
class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20))
    __mapper_args__ = {"polymorphic_on": type, "polymorphic_identity": "employee"}

class Manager(Employee):
    __mapper_args__ = {"polymorphic_identity": "manager"}

# 联合继承（每类一张表）
# 具体表继承（每类一张完整的表）
```

### 11.5 反射（不定义模型直接用已有表）

```python
from sqlalchemy import Table, MetaData

metadata = MetaData()
users = Table("users", metadata, autoload_with=engine)   # 自动读取现有表结构
print(users.c.name)
```

### 11.6 `__mapper_args__` 常用配置

```python
class User(Base):
    __mapper_args__ = {
        "version_id_col": version,           # 乐观锁
        "polymorphic_on": type,              # 单表继承的判别列
        "polymorphic_identity": "user",      # 本类的身份值
        "order_by": "User.name",             # 查询默认排序
        "eager_defaults": True,              # 插入后立即加载默认值
        "confirm_deleted_rows": True,        # 删除时确认影响行数
    }
```

---

## 十二、异步模式

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db", echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def main():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(User(name="alice"))
        # 查询
        result = await session.scalars(select(User).where(User.name == "alice"))
        user = result.first()
        # 预加载
        from sqlalchemy.orm import selectinload
        stmt = select(User).options(selectinload(User.todos))
        users = (await session.scalars(stmt)).all()

asyncio.run(main())
```

**要点**：

- 驱动必须换异步版本（`asyncpg` / `aiomysql` / `aiosqlite`）
- 所有 IO 操作都要 `await`
- 懒加载不能用了，必须显式 `selectinload` / `joinedload`
- FastAPI 集成时依赖注入 `AsyncSession`，路由用 `async def`

### 异步 vs 同步的选择

| 场景 | 推荐 |
|---|---|
| FastAPI + 高并发 IO | 异步（asyncpg） |
| 脚本 / CLI / 批处理 | 同步（psycopg2 / PyMySQL） |
| CPU 密集型 | 同步（异步没优势） |
| 学习 / 原型 | 同步（简单） |

---

## 十三、与 Alembic 配合

Alembic 就是给 SQLAlchemy 模型做版本控制。关键点：

```python
# env.py
from myapp.models import Base
target_metadata = Base.metadata    # ← 挂上模型的 metadata，autogenerate 才能对比
```

`alembic revision --autogenerate` 会对比 `Base.metadata` 和数据库反射出来的 schema，生成迁移脚本。详见 [ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md)。

### 命名约定（强烈推荐）

```python
from sqlalchemy import MetaData

NAMING_CONVENTION = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

从此所有约束名可预测、可复现，Alembic autogenerate 出的 `op.drop_constraint("uq_users_email", ...)` 在任何数据库上都成立。

---

## 十四、测试策略

### 14.1 SQLite 内存库（快，但方言差异大）

```python
# conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
```

### 14.2 真实数据库（testcontainers）

```python
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def pg_engine():
    with PostgresContainer("postgres:16") as pg:
        engine = create_engine(pg.get_connection_url())
        yield engine
        engine.dispose()
```

### 14.3 测试用什么数据库

| 场景 | 推荐 |
|---|---|
| 单元测试 | SQLite 内存库（快，但方言差异大） |
| 集成测试 | 真实的 PostgreSQL/MySQL（用 testcontainers） |
| 端到端测试 | 和生产同版本的数据库 |

---

## 十五、常见坑清单

| 坑 | 解决 |
|---|---|
| **N+1 查询** | 用 `selectinload` / `joinedload` 预加载关系 |
| **`DetachedInstanceError`** | session 关闭后访问懒加载属性。用 `expire_on_commit=False` + 提前预加载 |
| **MySQL 8 小时断连** | `pool_recycle=3600` + `pool_pre_ping=True` |
| **`String` 不给长度** | MySQL 会报错。`String(255)` 必须写长度 |
| **自增 ID `flush` 前是 None** | `session.add()` 后必须 `flush()` 或 `commit()` 才能读 ID |
| **`default` vs `server_default` 混淆** | 生产用 `server_default`（DDL 可见，任何客户端插入都生效） |
| **`UniqueConstraint` 只在应用层检查** | 必须在数据库层加 `unique=True`，否则并发下会重复 |
| **ORM 里写 SQL 字符串拼接** | 永远用绑定参数，防注入 |
| **`session.query()`（1.x 老 API）** | 2.0 用 `session.scalars(select(...))` |
| **SQLite 的 `alter_column` 不生效** | 用 `with op.batch_alter_table(...)` |
| **JSON 字段跨库差异** | MySQL 5.7+ / PG 9.2+ 才支持原生 JSON；用 `sqlalchemy.JSON` 通用类型 |
| **`relationship` 前向引用** | 用字符串 `"Todo"`；可空时 `Mapped["User \| None"]` 整体加引号 |
| **`session.commit()` 后对象属性变懒加载** | 默认 `expire_on_commit=True`，改成 `False` |
| **多个 Session 共享对象** | 一个对象只能属于一个 Session。跨 Session 传递用 `session.merge(obj)` |
| **`selectin` 集合太大** | IN 子句有元素数上限（Oracle 1000），大集合分批 |
| **DDL 不能事务回滚（MySQL）** | Alembic 迁移失败时 `alembic_version` 可能没更新，需人工介入 |
| **`cascade` 忘配** | 删父时子不删，留下孤儿外键。用 `cascade="all, delete-orphan"` |
| **`backref` vs `back_populates`** | 2.0 推荐 `back_populates`（显式，两端都写） |

---

## 十六、性能优化清单

1. **连接池调优**：`pool_size` / `max_overflow` / `pool_recycle` / `pool_pre_ping`
2. **`echo=False`**：生产环境关掉 SQL 日志
3. **预加载关系**：`selectinload` > `joinedload` > 默认 `lazy="select"`
4. **批量插入**：`session.bulk_insert_mappings` 或 `conn.execute(insert(t), list_of_dicts)`
5. **只查需要的列**：`select(User.id, User.name)` 而不是 `select(User)`
6. **加索引**：`index=True` 或 `Index("ix_...", col1, col2)`
7. **`yield_per`**：大结果集分批读，避免一次性加载到内存

    ```python
    result = session.scalars(select(User).yield_per(1000))
    for user in result:
        ...
    ```

8. **`execution_options`**：`populate_existing=True` 强制覆盖 identity map
9. **避免 ORM 事件滥用**：`before_flush` 里做重活会拖慢每次 flush
10. **慢查询日志**：MySQL `slow_query_log=ON` + SQLAlchemy `before_cursor_execute` 事件打点
11. **用 `selectin` 而不是 `joined` 加载大集合**：避免笛卡尔积爆炸
12. **批量删除用 `delete().where(...)` 而不是逐个 `session.delete()`**

---

## 附录 A：本项目内的 SQLAlchemy 落地实证

以下是本仓库（`e:\python_learn`）里已经存在的 SQLAlchemy 实现，可作为对照参考：

### 持久层主包（Day 15~17）

| 模块 | 职责 |
|---|---|
| [day15_orm/models.py](./day15_orm/models.py) | 表定义：`User` / `Todo` / `Tag` + 中间表 `todo_tags` |
| [day15_orm/database.py](./day15_orm/database.py) | Engine / Session / 建表 / 上下文管理 |
| [day15_orm/db_config.py](./day15_orm/db_config.py) | 连接串组装（本地私密配置从 `db_config_local.py` 读，不进 Git） |
| [day15_orm/__init__.py](./day15_orm/__init__.py) | 把子模块的公开名字提上来 |

### DAO 层

| 模块 | 职责 |
|---|---|
| [day16_crud/dao.py](./day16_crud/dao.py) | 单表 CRUD |
| [day17_relationship/dao.py](./day17_relationship/dao.py) | 关联/分页（`selectinload` / `count` / `limit` / `offset`） |

### 一键验证脚本

| 脚本 | 覆盖内容 |
|---|---|
| [run_day15_demo.py](./run_day15_demo.py) | 版本 / 连通性 / 建表 / 列反射 / DDL 编译 / 事务回滚 |
| [run_day16_demo.py](./run_day16_demo.py) | CRUD 全流程 + `IntegrityError` 唯一约束 |
| [run_day17_demo.py](./run_day17_demo.py) | Schema 迁移 / 一对多 / `back_populates` 同步 / 懒加载 vs `selectinload` / 多对多 / 分页 / `ON DELETE SET NULL` |

### 本项目踩过的坑（已验证）

1. **自增主键要 `commit` / `flush` 之后才能读到**——`session.add()` 后 `user.id` 是 `None`，必须 `flush()` 或 `commit()` 才能拿到数据库生成的 ID。

2. **`String` 必须给长度**——MySQL 的 `VARCHAR` 不给长度会直接报错，不像某些数据库可以偷懒。

3. **`server_default=func.now()` vs `default=datetime.now`**——前者写进 DDL，由数据库填值；后者只在 Python 端填。生产推荐 `server_default`。

4. **`relationship` 前向引用要整体加引号**——Python 3.14 上 `Mapped["User | None"]` 整体加引号，单独给 `None` 加引号会报错。

5. **`selectinload` 解决 N+1**——[day17_relationship/dao.py](./day17_relationship/dao.py) 里的 `get_user_with_todos` 用 `selectinload(User.todos)` 一次性预加载，避免循环里逐个访问触发 N 条 SQL。

6. **`ON DELETE SET NULL` 是数据库层行为**——[models.py L219](./day15_orm/models.py) 里的 `ForeignKey("users.id", ondelete="SET NULL")` 写进 DDL，删 User 时 Todo.owner_id 自动变 NULL，不依赖 ORM 是否加载。

---

## 附录 B：与 Pydantic / FastAPI / Alembic 的集成链路

```
┌──────────────────────────────────────────────────────────┐
│  FastAPI 路由（todo_api/routers/*.py）                    │
│    ↓ 依赖注入 Session / AsyncSession                     │
├──────────────────────────────────────────────────────────┤
│  DAO 层（day16_crud/dao.py、day17_relationship/dao.py）   │
│    ↓ select() / session.execute()                        │
├──────────────────────────────────────────────────────────┤
│  SQLAlchemy ORM 模型（day15_orm/models.py）              │
│    ↓ Base.metadata                                       │
├──────────────────────────────────────────────────────────┤
│  Alembic（day18_alembic/）                                │
│    · env.py 里 target_metadata = Base.metadata           │
│    · autogenerate 对比模型 vs 数据库                      │
│    · versions/*.py 记录 schema 演进                       │
├──────────────────────────────────────────────────────────┤
│  Pydantic 接口模型（todo_api/schemas.py）                │
│    · ConfigDict(from_attributes=True)                    │
│    · 直接吃 ORM 对象，做响应序列化                        │
└──────────────────────────────────────────────────────────┘
```

**关键集成点**：

- **SQLAlchemy → Alembic**：`Base.metadata` 是 Alembic autogenerate 的对比基准。
- **SQLAlchemy → Pydantic**：`ConfigDict(from_attributes=True)` 让 Pydantic 直接吃 ORM 对象。
- **SQLAlchemy → FastAPI**：`yield session` 依赖注入模式，和 Alembic 的 `session_scope` 是同一套上下文管理思想。
- **Pydantic → FastAPI**：`response_model=TaskOut` 自动序列化 + 过滤多余字段 + 生成 OpenAPI 文档。

---

## 参考

- 官方文档：<https://docs.sqlalchemy.org/en/20/>
- 2.0 教程：<https://docs.sqlalchemy.org/en/20/tutorial/>
- ORM 映射：<https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html>
- 查询指南：<https://docs.sqlalchemy.org/en/20/orm/queryguide/>
- 1.x → 2.0 迁移：<https://docs.sqlalchemy.org/en/20/changelog/migration_20.html>
- 本项目锁定的版本：`SQLAlchemy==2.0.52`（见 [requirements.txt](./requirements.txt)）
- 配套文档：[PYDANTIC_GUIDE.md](./PYDANTIC_GUIDE.md)、[ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md)、[DEPENDENCIES.md](./DEPENDENCIES.md)
