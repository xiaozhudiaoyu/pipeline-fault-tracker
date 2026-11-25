# Alembic 完整用法速查

> 基于 Alembic 1.20.0（本项目锁定版本，见 [requirements.txt](./requirements.txt)），从入门到能干活。所有 API 均为 1.x 稳定接口。
>
> 本文档由 Qoder 会话整理落盘，作为项目内 Alembic 用法的通用参考；附录部分给出本仓库的实证落地。

---

## 一、Alembic 解决什么问题

SQLAlchemy 的 `Base.metadata.create_all()` 只能"从空库建出当前模型对应的表"，做不到：

- 已有库加一列 / 改类型 / 加索引
- 变更有版本、可回退、可审计
- 多人协作时按顺序合并 schema 变更
- 生产环境上按顺序重放变更

Alembic 就是**给 schema 变更做版本控制**：每次改模型生成一个"迁移脚本"（一个 revision），脚本里写清楚 `upgrade()` 和 `downgrade()`，数据库里维护一张 `alembic_version` 表记录"当前处于哪个 revision"。

**核心价值**：让 schema 演进从"人肉记 SQL"变成"可 diff、可回滚、可重放的代码"。

---

## 二、安装与生态

```bash
pip install alembic                # 核心
pip install alembic[tz]            # 带时区支持（渲染日期用 ZoneInfo）
```

**依赖关系**：

- `SQLAlchemy>=1.4` —— Alembic 1.x 的最低要求（推荐 2.0+）
- `Mako` —— 迁移脚本模板引擎
- `MarkupSafe` —— Mako 的传递依赖
- `typing-extensions` —— 类型兼容层

Alembic 本身不带数据库驱动，驱动跟着 SQLAlchemy 走（PyMySQL / psycopg / asyncpg 等）。

---

## 三、核心概念

| 概念 | 含义 |
|---|---|
| **revision** | 一次 schema 变更，一个 `.py` 文件，有唯一 ID（默认 12 位十六进制） |
| **down_revision** | 上一个 revision 的 ID，把所有 revision 串成单向链表 |
| **head** | 链路末端（最新）的 revision |
| **base** | 链路起点（`down_revision = None` 的那个） |
| **`alembic_version` 表** | 数据库里存的一张小表，记录当前库停在哪个 revision |
| **autogenerate** | 对比 `target_metadata`（Python 模型）和实际库结构的差异，自动生成迁移脚本 |
| **env.py** | 迁移运行环境，每次 `alembic xxx` 命令都会先跑一遍它 |
| **script.py.mako** | 生成新 revision 文件的模板 |
| **offline mode** | 只输出 SQL 不连库（`alembic upgrade head --sql`） |
| **online mode** | 真连库执行（默认） |
| **branch / merge** | 多人协作时并行开发形成分支，用 merge revision 汇合 |

---

## 四、标准工作流

```
① alembic init <目录>            # 一次性：生成 alembic.ini + 迁移目录
② 编辑 alembic.ini                # 配 sqlalchemy.url、script_location
③ 编辑 <目录>/env.py              # 挂 target_metadata = Base.metadata
④ 改模型（models.py）
⑤ alembic revision --autogenerate -m "add xxx"    # 生成迁移脚本
⑥ 人工审查脚本（autogenerate 不是万能的）
⑦ alembic upgrade head            # 应用到数据库
⑧ 出问题时：alembic downgrade -1  # 回退一步
```

**首次接入已有库的变体**（库里表已经存在）：

```
① alembic init <目录>
② 配 env.py（挂 metadata）
③ 手写一份"基线 revision"（完整的 CREATE TABLE 语句）
④ alembic stamp head                # 打标记，不真跑 SQL
⑤ 之后正常走 revision → upgrade 流程
```

---

## 五、命令完整清单

### 5.1 版本查询

```bash
alembic current                    # 库里当前是哪个 revision
alembic current --verbose          # 附带 revision 的 message、时间
alembic history                    # 完整链路（base → head）
alembic history --verbose          # 每一步的详细信息
alembic history -r current:head    # 只看当前到 head 的区间
alembic heads                      # 所有分支的头（多分支时会有多个）
alembic branches                   # 显示分支结构
alembic show <rev>                 # 看某个 revision 的详情
```

### 5.2 生成迁移

```bash
alembic revision -m "message"                              # 生成空脚本，手写 upgrade/downgrade
alembic revision --autogenerate -m "message"               # 自动对比生成
alembic revision --autogenerate --rev-id myrev01 -m "..."  # 自定义 revision ID
alembic revision --head <rev> -m "..."                     # 指定从哪个 head 派生（多分支时）
alembic revision --sql -m "..."                            # 生成 SQL 文件而不是 Python 脚本
```

### 5.3 应用与回滚

```bash
alembic upgrade head                  # 升到最新
alembic upgrade +1                    # 只升一步
alembic upgrade <rev>                 # 升到指定 revision
alembic downgrade -1                  # 回退一步
alembic downgrade base                # 回退到起点（等于清空所有变更）
alembic downgrade <rev>               # 回退到指定 revision
```

### 5.4 打标记（不跑 SQL）

```bash
alembic stamp head                    # 把已有库"认领"到 head，不执行 upgrade
alembic stamp <rev>                   # 认领到指定 revision
alembic stamp head --purge            # 先清 alembic_version 再打标记
alembic stamp base                    # 回到"没有版本"状态
```

**典型场景**：项目引入 Alembic 之前，库里已经有表了。手写一份基线 revision 之后，用 `stamp head` 让 Alembic 认为"当前已经在最新版"，而不是跑一遍 CREATE TABLE 报"表已存在"。

### 5.5 离线模式（只出 SQL 不连库）

```bash
alembic upgrade head --sql             # 打印从当前到 head 的 SQL，不执行
alembic upgrade base:head --sql        # 从 base 到 head 的完整 SQL
alembic upgrade <rev1>:<rev2> --sql    # 指定区间的 SQL
alembic downgrade head:-1 --sql        # 回退一步的 SQL
```

适合把 SQL 交给 DBA 审核后再手动执行；也适合生成部署脚本给不能直连数据库的运维环境。

### 5.6 多分支合并

```bash
alembic merge <rev1> <rev2> -m "merge branches"    # 生成一个 merge revision
alembic heads                                       # 先看有哪些 head
```

### 5.7 编辑与清理

```bash
alembic edit <rev>                    # 用 $EDITOR 打开某个 revision
alembic check                         # 检查模型与库是否一致（1.9+）
```

### 5.8 初始化模板

```bash
alembic init <目录>                    # 通用模板（同步）
alembic init -t async <目录>           # 异步模板（create_async_engine）
alembic init -t multidb <目录>         # 多数据库模板
```

---

## 六、迁移脚本骨架

```python
"""add priority column to todos

Revision ID: a1b2c3d4e5f6
Revises: 0123456789ab
Create Date: 2026-09-20 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0123456789ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('todos', sa.Column('priority', sa.Integer(), nullable=False, server_default='2'))
    op.create_index('ix_todos_priority', 'todos', ['priority'])


def downgrade() -> None:
    op.drop_index('ix_todos_priority', table_name='todos')
    op.drop_column('todos', 'priority')
```

### 四个元字段

| 字段 | 含义 |
|---|---|
| `revision` | 本脚本的唯一 ID（字符串） |
| `down_revision` | 上一个 revision 的 ID；`None` = 链路起点；元组 = merge revision |
| `branch_labels` | 分支标签（多分支合并时用） |
| `depends_on` | 显式依赖（罕用，用于跨分支依赖） |

### 四条铁律

1. **`upgrade` 和 `downgrade` 严格互逆**——否则回滚时会破坏数据一致性。
2. **不要改已经 push 到远端、别人可能已经跑过的 revision**——要改就新建一个。
3. **schema 变更和数据变更分开成不同 revision**——回滚粒度更清晰。
4. **加 NOT NULL 列时必须给 `server_default`**——否则已有行会失败。

---

## 七、`op.*` 常用操作速查

### 7.1 表

```python
op.create_table(
    'users',
    sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column('name', sa.String(50), nullable=False, unique=True),
    sa.Column('email', sa.String(120)),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    mysql_engine='InnoDB',           # 方言专属参数
    mysql_charset='utf8mb4',
)
op.drop_table('users')
op.rename_table('old_name', 'new_name')
```

### 7.2 列

```python
# 加列
op.add_column('t', sa.Column('c', sa.String(50), nullable=True))
op.add_column('t', sa.Column('c', sa.Integer(), nullable=False, server_default='0'))

# 删列
op.drop_column('t', 'c')

# 改列（最复杂，参数最多）
op.alter_column(
    't', 'c',
    existing_type=sa.String(50),        # 原类型（必填，Alembic 不知道）
    type_=sa.String(100),               # 新类型
    existing_nullable=False,            # 原可空性
    nullable=True,                      # 新可空性
    new_column_name='c2',               # 重命名
    existing_server_default=sa.text("'x'"),
    server_default=sa.text("'y'"),
    existing_comment='old',
    comment='new',
)
```

### 7.3 约束

```python
op.create_unique_constraint('uq_t_name', 't', ['name'])
op.drop_constraint('uq_t_name', 't', type_='unique')

op.create_foreign_key('fk_t_uid', 't', 'users', ['uid'], ['id'], ondelete='CASCADE')
op.drop_constraint('fk_t_uid', 't', type_='foreignkey')

op.create_primary_key('pk_t', 't', ['id'])
op.drop_constraint('pk_t', 't', type_='primary')

op.create_check_constraint('ck_t_age', 't', 'age >= 0')
op.drop_constraint('ck_t_age', 't', type_='check')
```

### 7.4 索引

```python
op.create_index('ix_t_c', 't', ['c'], unique=False)
op.create_index('ix_t_multi', 't', ['a', 'b', 'c'])
op.drop_index('ix_t_c', table_name='t')
```

### 7.5 原生 SQL / 数据迁移

```python
op.execute("UPDATE t SET c = 'x' WHERE c IS NULL")
op.execute(sa.text("DELETE FROM t WHERE id < :min_id"), execution_options={"parameters": {"min_id": 100}})

# 批量插入（用匿名表定义结构）
op.bulk_insert(
    sa.table('t',
             sa.column('id', sa.Integer),
             sa.column('name', sa.String)),
    [
        {'id': 1, 'name': 'a'},
        {'id': 2, 'name': 'b'},
    ],
)
```

### 7.6 批量模式（SQLite 必备）

SQLite 的 `ALTER TABLE` 支持很弱（不能改类型、不能删列、不能加约束），Alembic 用"建新表 → 拷数据 → 删旧表 → 改名"的方式绕过：

```python
with op.batch_alter_table('t') as batch_op:
    batch_op.alter_column('c', existing_type=sa.String(50), type_=sa.String(100))
    batch_op.create_index('ix_c', ['c'])
    batch_op.drop_column('old_c')
```

MySQL / PostgreSQL 不需要 batch 模式。`env.py` 里设 `render_as_batch=True` 可以让 autogenerate 自动用 batch。

---

## 八、`env.py` 关键配置

`env.py` 是 Alembic 的运行环境入口，`context.configure(...)` 里的开关决定 autogenerate 精度：

```python
from alembic import context
from sqlalchemy import create_engine, pool
from myapp.models import Base

config = context.config
target_metadata = Base.metadata          # ← 必须挂上，否则 autogenerate 什么都对比不出

def run_migrations_online() -> None:
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,         # 迁移用完就关，不池化
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,

            # ── autogenerate 对比精度 ───────────────────────────
            compare_type=True,             # 检测列类型变化（VARCHAR(50) → VARCHAR(100)）
            compare_server_default=True,   # 检测默认值变化（MySQL 上不完全可靠）

            # ── 管辖范围过滤 ────────────────────────────────────
            include_object=include_object,         # 对象级过滤（表/列/索引）
            include_name=include_name,             # 名字级过滤（1.5+，比 include_object 更早触发）
            include_schemas=False,                 # 是否包含 schema（PostgreSQL 的 schema）
            version_table='alembic_version',       # 版本表名（默认，可改）
            version_table_schema=None,             # 版本表放哪个 schema

            # ── 渲染定制 ───────────────────────────────────────
            render_as_batch=False,         # SQLite 需要 True；MySQL/PG 保持 False
            render_item=render_item,       # 自定义类型/默认值的渲染
            process_revision_directives=process_revision_directives,   # 后处理生成的脚本

            # ── 事务与命名 ─────────────────────────────────────
            transactional_ddl=True,        # 迁移是否包在事务里（PG 默认 True，MySQL DDL 隐式提交）
            transaction_per_migration=False,  # 每个迁移单独一个事务（默认所有迁移共用一个）
            as_sql=False,                  # offline 模式用 True
            literal_binds=False,           # offline 输出 SQL 时把绑定参数展开成字面量
        )
        with context.begin_transaction():
            context.run_migrations()
```

### `include_object` 过滤器（保护"外来表"）

场景：库里除了本项目的表，还有别的项目 / 早期实验遗留的表。autogenerate 默认会把"库里有但模型里没有"的表判定为多余，生成 `op.drop_table()` 删掉它们。

```python
FOREIGN_TABLES = {"legacy_user", "temp_account"}

def include_object(object, name, type_, reflected, compare_to) -> bool:
    """返回 False 表示：这个对象当作不存在，不参与对比。"""
    if type_ == "table" and name in FOREIGN_TABLES:
        return False
    return True
```

### `render_item` 自定义渲染

场景：autogenerate 生成的类型表达式不是你想要的（比如自定义类型）。

```python
def render_item(type_, obj, autogen_context):
    """返回 False 用默认渲染；返回字符串用自定义渲染。"""
    if type_ == "type" and isinstance(obj, MyCustomType):
        return "myapp.types.MyCustomType()"
    return False
```

### `process_revision_directives` 后处理

场景：autogenerate 生成了空迁移（没有实际变更），自动改成 `pass` 或者直接删除。

```python
def process_revision_directives(context, revision, directives):
    if config.cmd_opts and config.cmd_opts.autogenerate:
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []        # 不生成文件
```

---

## 九、命名约定（`naming_convention`）

不加约定的话，`UniqueConstraint` 生成的名字是数据库随机的（MySQL 是 `t_col_key`，PostgreSQL 是 `t_col_key`，SQLite 又是另一套）。以后想 `drop_constraint` 就要先反射查名字，很痛。

**在 SQLAlchemy 的 `models.py` 里加**（Alembic 会自动继承）：

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

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

## 十、`alembic.ini` 关键项

```ini
[alembic]
script_location = alembic                    # 迁移脚本目录（相对 ini 或绝对路径）
prepend_sys_path = .                          # 让 env.py 能 import 项目模块
path_separator = os                           # version_locations 的分隔符

file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(rev)s_%%(slug)s
                                              # 文件名带日期，方便排序
truncate_slug_length = 40                     # message 截断长度
timezone = Asia/Shanghai                      # 需要 alembic[tz]
revision_environment = false                  # revision 命令是否要跑 env.py
sourceless = false                            # 是否允许只有 .pyc 的 revision
output_encoding = utf-8                       # 生成脚本的编码
version_path_separator = os                   # 已废弃，用 path_separator

# 连接串。也可以留空，在 env.py 里从环境变量 / .env / 项目配置里读
sqlalchemy.url = postgresql+psycopg://user:pass@localhost/db

# 生成新 revision 后自动跑 formatter（可选）
[post_write_hooks]
hooks = ruff
ruff.type = module
ruff.module = ruff
ruff.options = format REVISION_SCRIPT_FILENAME

# 日志配置（Python logging fileConfig 格式）
[loggers]
keys = root,sqlalchemy,alembic

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine
```

### 安全要点

**`alembic.ini` 通常进 Git，密码不能写在里面。** 生产做法：

```python
# env.py 里覆盖 ini 的 URL
import os
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
```

或者：

```ini
# alembic.ini 里只留占位符
sqlalchemy.url = driver://user:pass@localhost/dbname
```

### 中文 Windows 的编码坑

**`alembic.ini` 必须保持纯 ASCII**（含注释）——Alembic 用 OS locale 编码读它（中文 Windows 是 GBK），写 UTF-8 中文注释会直接 `UnicodeDecodeError`。中文讲解全部挪到 `env.py`（Python 源码按 UTF-8 读，无碍）。

---

## 十一、异步模式（`create_async_engine`）

用 `alembic init -t async <目录>` 生成异步模板，或者手动改 `env.py`：

```python
import asyncio
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context

config = context.config
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations(connectable):
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    asyncio.run(run_async_migrations(connectable))

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**要点**：驱动必须换异步版本（`postgresql+asyncpg://`、`mysql+aiomysql://`、`sqlite+aiosqlite://`）。

---

## 十二、Python API（不走命令行）

### 12.1 用 `alembic.command` 跑迁移

```python
from alembic import command
from alembic.config import Config

cfg = Config("/path/to/alembic.ini")
cfg.set_main_option("script_location", "/path/to/migrations")
cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://user:pass@localhost/db")

command.upgrade(cfg, "head")
command.downgrade(cfg, "-1")
command.revision(cfg, message="add xxx", autogenerate=True)
command.stamp(cfg, "head")
command.current(cfg, verbose=True)
command.history(cfg, verbose=True)
command.heads(cfg, verbose=True)
command.merge(cfg, "rev1 rev2", message="merge branches")
command.check(cfg)                       # 1.9+：模型与库一致性检查
```

### 12.2 用底层 API 读版本信息

```python
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

script = ScriptDirectory.from_config(cfg)
engine = create_engine(url)

with engine.connect() as conn:
    ctx = MigrationContext.configure(conn)
    current_rev = ctx.get_current_revision()     # 库里的当前版本（None = 尚未初始化）

head_rev = script.get_current_head()              # 代码里的最新版本
is_up_to_date = current_rev == head_rev

# 遍历所有 revision
for rev in script.walk_revisions():
    print(rev.revision, rev.down_revision, rev.doc)

# 获取两个 revision 之间的差异
from alembic.script import ScriptDirectory
revs = list(script.iterate_revisions("head", "base"))
```

### 12.3 纯代码构造 Config（不依赖 ini 文件）

```python
from alembic.config import Config
from alembic import command

cfg = Config()                                   # 不传 ini 路径
cfg.set_main_option("script_location", "migrations")
cfg.set_main_option("sqlalchemy.url", "sqlite:///./app.db")
cfg.attributes["configure_logger"] = False       # 不覆盖已有的 logging 配置

command.upgrade(cfg, "head")
```

---

## 十三、autogenerate 的能力边界

### 能检测（开箱即用）

- 加 / 删表
- 加 / 删列
- 改列可空性
- 改主键
- 加 / 删索引
- 加 / 删唯一约束
- 加 / 删外键

### 需要开关才检测

| 开关 | 检测内容 |
|---|---|
| `compare_type=True` | 改列类型（VARCHAR(50) → VARCHAR(100)） |
| `compare_server_default=True` | 改默认值（MySQL 上不可靠，PG 上准确） |

### 检测不到（必须手写）

- 表 / 列重命名（会当成"删一个 + 加一个"）
- 数据迁移（`UPDATE ... SET ...`）
- 复合约束的调整顺序
- 触发器、存储过程、视图
- CHECK 约束的变化（1.x 部分支持）
- 自定义类型的内部变化

### 手写"重命名"的正确姿势

```python
def upgrade() -> None:
    op.alter_column(
        'users', 'name',
        new_column_name='full_name',
        existing_type=sa.String(50),
        existing_nullable=False,
    )

def downgrade() -> None:
    op.alter_column(
        'users', 'full_name',
        new_column_name='name',
        existing_type=sa.String(50),
        existing_nullable=False,
    )
```

### autogenerate 后的审查清单

- [ ] 有没有意外的 `op.drop_*`（可能是 metadata 没挂全）
- [ ] 有没有意外的 `op.create_table`（可能是反射到了其他 schema）
- [ ] `op.alter_column` 的 `existing_*` 参数对不对
- [ ] NOT NULL 列有没有 `server_default`
- [ ] downgrade 是不是 upgrade 的严格逆操作

---

## 十四、多分支与 merge

### 场景

两个同事各自拉了 head=A，分别生成 B 和 C，push 后你 pull 下来就有两个 head。

```bash
alembic heads
# b1c2d3 (head)
# e4f5g6 (head)
```

### 合并

```bash
alembic merge b1c2d3 e4f5g6 -m "merge user and order branches"
# 生成一个 merge revision，down_revision = ('b1c2d3', 'e4f5g6')

alembic upgrade head
```

### merge revision 长什么样

```python
"""merge user and order branches

Revision ID: m1e2r3g4e5
Revises: b1c2d3, e4f5g6
"""
revision = 'm1e2r3g4e5'
down_revision = ('b1c2d3', 'e4f5g6')      # 元组！
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass                                   # 一般是空的

def downgrade() -> None:
    pass
```

merge revision 只是把两条链汇合，不执行任何 schema 变更。

### 预防多分支

CI 里加一步：

```bash
HEADS=$(alembic heads | wc -l)
if [ "$HEADS" -gt 1 ]; then
    echo "多个 head，请先 merge"; exit 1
fi
```

---

## 十五、数据迁移的标准套路

**一个 revision 只做一件事**，分开的好处：任一步失败可以精确回退到上一步，不用整个重来。

### 例：把 `first_name` + `last_name` 合并成 `full_name`

```
rev A: op.add_column('users', sa.Column('full_name', sa.String(100), nullable=True))
rev B: op.execute("UPDATE users SET full_name = CONCAT(first_name, ' ', last_name)")
rev C: op.alter_column('users', 'full_name', nullable=False, existing_type=sa.String(100))
rev D: op.drop_column('users', 'first_name')
       op.drop_column('users', 'last_name')
```

### 例：枚举值迁移

```python
# rev A: 加新列
op.add_column('orders', sa.Column('status_new', sa.String(20), nullable=True))

# rev B: 拷贝并映射
op.execute("""
    UPDATE orders SET status_new = CASE status_old
        WHEN 'pending' THEN 'PENDING'
        WHEN 'done' THEN 'COMPLETED'
        ELSE 'UNKNOWN'
    END
""")

# rev C: 删旧列、重命名新列
op.drop_column('orders', 'status_old')
op.alter_column('orders', 'status_new',
                new_column_name='status',
                existing_type=sa.String(20),
                nullable=False)
```

### 大表数据迁移的坑

- **不要在一个事务里改百万行**——用分批 UPDATE（LIMIT + 循环）
- **MySQL DDL 隐式提交**——数据迁移和 schema 迁移必须分开
- **长时间锁表**——生产环境用 `pt-online-schema-change` / `gh-ost`
- **downgrade 里的数据迁移**——往往不可逆（比如删了列，数据就丢了），downgrade 里只能 `pass` 或抛异常

---

## 十六、生产环境的常见坑

| 坑 | 说明 / 解决 |
|---|---|
| **MySQL DDL 不能事务回滚** | `ALTER TABLE` 会隐式提交。迁移失败后 `alembic_version` 可能没更新但表已改，需要人工介入。 |
| **大表加列会锁表** | MySQL 5.6 前 `ALTER TABLE` 全表锁；5.6+ 有 online DDL 但仍需谨慎。生产环境用 `pt-online-schema-change` / `gh-ost`。 |
| **`alembic.ini` 里的密码进 Git** | 用环境变量替代，见第十节。 |
| **`--autogenerate` blindly 采纳** | 一定要人工审查生成的脚本，特别是 `drop_*` 操作。 |
| **多 head 未 merge 就部署** | CI 里加 `alembic heads \| wc -l` 检查。 |
| **`alembic_version` 表被误删** | 用 `alembic stamp` 恢复。 |
| **不同环境 schema 漂移** | 生产库跑过手动 SQL 但代码里没记录 → autogenerate 会生成"重复"的迁移。要么 `stamp`，要么补一个 revision。 |
| **中文 Windows 的编码坑** | `alembic.ini` 用 OS locale 编码读取（GBK），非 ASCII 注释会 `UnicodeDecodeError`。所有 `.ini` 保持 ASCII。 |
| **`env.py` 忘记 `prepend_sys_path = .`** | 导致 `from myapp.models import Base` 报 `ModuleNotFoundError`。 |
| **`target_metadata = None`** | autogenerate 永远生成空脚本。必须挂上 `Base.metadata`。 |
| **`compare_type` 忘开** | 改列类型检测不到。 |
| **`render_as_batch` 在 SQLite 上忘开** | `alter_column` 报错。 |
| **`server_default` 写成 Python 表达式** | `server_default=func.now()` 对；`server_default=datetime.now()` 错（后者是 Python 端求值）。 |
| **`downgrade` 不写或写错** | 回滚时炸掉。每个 revision 都要能 downgrade。 |
| **多数据库共享一个 `alembic_version` 表** | 用 `version_table_schema` 或 `version_table` 参数区分。 |

---

## 十七、与 pytest 集成（测试用迁移）

```python
# conftest.py
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

@pytest.fixture
def migrated_engine(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")        # 用真实迁移建库，不用 create_all
    engine = create_engine(db_url)
    yield engine
    command.downgrade(cfg, "base")      # 顺便验证 downgrade 也能跑通
    engine.dispose()
```

**好处**：每次 CI 都会验证 upgrade 和 downgrade 双向都能跑，及早发现"downgrade 写坏了"的问题。

### 检查模型与库一致性

```python
# 在测试里
def test_no_pending_migrations(migrated_engine):
    """确保模型没有未生成迁移的变更。"""
    cfg = Config("alembic.ini")
    # alembic check 会在有差异时抛异常（1.9+）
    command.check(cfg)
```

---

## 十八、性能与最佳实践

### 迁移脚本组织

- **按时间顺序命名**：`file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(rev)s_%%(slug)s`，一眼看出顺序。
- **一个 revision 只做一件事**：加列 / 改类型 / 数据回填分开。
- **message 写清楚**：`add priority column to todos`，不要 `update`。

### CI 集成

```bash
# 每次 PR 都跑
alembic heads | wc -l | grep -q "^1$" || (echo "多 head"; exit 1)
alembic upgrade head --sql > /dev/null      # 离线跑一遍，验证 SQL 能生成
alembic check                                # 模型与库一致
pytest                                       # 测试里跑 upgrade + downgrade
```

### 部署策略

- **蓝绿部署**：新实例跑 `alembic upgrade head`，老实例保持原版本，切流量后老实例再升。
- **滚动部署**：迁移必须先向后兼容（加列可以，删列不行），等所有实例升完再发第二个版本删列。
- **备份**：跑迁移前必须备份数据库。回退代码不等于回退数据。

### 日志与监控

- `alembic.ini` 里把 `[logger_alembic] level = INFO`，能看到每个 revision 的执行。
- 生产环境用 `--sql` 模式生成 SQL，交给 DBA 审核后手动执行。
- 迁移耗时监控：大表加列可能跑几分钟到几小时。

---

## 附录 A：本项目内的 Alembic 落地实证

以下是本仓库（`e:\python_learn`）里已经存在的 Alembic 实现，可作为对照参考：

| 文件 | 职责 |
|---|---|
| [alembic.ini](./alembic.ini) | 全局配置（脚本目录、日志、URL 占位符）。**保持 ASCII**，中文注释都挪到 `env.py`；真实 URL 不写这里 |
| [day18_alembic/env.py](./day18_alembic/env.py) | 迁移运行环境：接模型的 metadata、接项目的连接串、autogenerate 过滤器 |
| [day18_alembic/script.py.mako](./day18_alembic/script.py.mako) | 生成迁移脚本的 Mako 模板 |
| [day18_alembic/versions/6ddbf4e09cce_baseline_initial_schema.py](./day18_alembic/versions/6ddbf4e09cce_baseline_initial_schema.py) | **基线**：手写完整的 4 张表 CREATE。`down_revision = None`，链路起点 |
| [day18_alembic/versions/1145bfe61b0a_add_priority_to_todos.py](./day18_alembic/versions/1145bfe61b0a_add_priority_to_todos.py) | 增量：给 `todos` 加 `priority` 列。autogenerate 生成 |
| [run_day18_demo.py](./run_day18_demo.py) | 一键验证脚本：用 `alembic.command` 的 Python API 跑完整 upgrade/downgrade 流程 |

### 本项目踩过的坑（已验证）

1. **`alembic.ini` 必须 ASCII-only**（[alembic.ini L90-L96](./alembic.ini)）——Alembic 用 OS locale 编码读它，中文 Windows 是 GBK，写 UTF-8 中文注释会直接 `UnicodeDecodeError`。中文讲解全部挪到 [env.py](./day18_alembic/env.py)。

2. **首次接入用 `alembic stamp head` 而不是 `upgrade head`**——库里表已经存在时，`stamp` 只写 `alembic_version` 表不真跑 SQL。

3. **基线要手写而不是 autogenerate**（[baseline L23-L33](./day18_alembic/versions/6ddbf4e09cce_baseline_initial_schema.py)）——因为 autogenerate 对"已存在且与模型一致"的表不会产 CREATE，得到的基线是空的，空库跑 `upgrade head` 建不出表。

4. **`include_object` 保护外来表**（[env.py L39-L57](./day18_alembic/env.py)）——共享库里如果有别人的表，autogenerate 会判定为"多余"生成 `drop_table`。用过滤器把它们排除在管辖外。

5. **真实 URL 不放 `alembic.ini`**——[alembic.ini L93-L97](./alembic.ini) 只是占位符，[env.py L18](./day18_alembic/env.py) 从 `day15_orm.db_config.build_url()` 拿真实连接串（本地私密配置，不进 Git）。

6. **`target_metadata = Base.metadata`**（[env.py L31](./day18_alembic/env.py)）——不挂这个，autogenerate 什么都对比不出来。

### ⭐本项目常用命令（PowerShell）

```powershell
# 查看当前版本
.\.venv\Scripts\alembic.exe current

# 查看迁移链路
.\.venv\Scripts\alembic.exe history --verbose

# 升级到最新
.\.venv\Scripts\alembic.exe upgrade head

# 回退一步
.\.venv\Scripts\alembic.exe downgrade -1

# 自动生成迁移
.\.venv\Scripts\alembic.exe revision --autogenerate -m "add xxx column"

# 打标记（首次接入）
.\.venv\Scripts\alembic.exe stamp head
```

---

## 附录 B：与 SQLAlchemy / FastAPI 的集成链路

```
┌──────────────────────────────────────────────────────────┐
│  FastAPI 路由（todo_api/routers/*.py）                    │
│    ↓ 依赖注入 AsyncSession / Session                     │
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

- Alembic 的 `env.py` 必须 import 项目的 `Base`，挂上 `target_metadata`。
- 项目的 `Base.metadata` 是 SQLAlchemy 模型的"图纸集合"，也是 Alembic autogenerate 的对比基准。
- Pydantic 的 `from_attributes=True` 让接口层直接吃 ORM 对象，不需要手动转字典。
- FastAPI 的 `yield session` 依赖注入模式，和 Alembic 的 `session_scope` 是同一套上下文管理思想。

---

## 参考

- 官方文档：<https://alembic.sqlalchemy.org/>
- 教程：<https://alembic.sqlalchemy.org/en/latest/tutorial.html>
- Cookbook（常见场景）：<https://alembic.sqlalchemy.org/en/latest/cookbook.html>
- API 参考：<https://alembic.sqlalchemy.org/en/latest/api.html>
- 本项目锁定的版本：`alembic==1.20.0`（见 [requirements.txt](./requirements.txt)）
- 配套文档：[PYDANTIC_GUIDE.md](./PYDANTIC_GUIDE.md)、[DEPENDENCIES.md](./DEPENDENCIES.md)
