"""add priority to pipeline_faults

Revision ID: b3e19c4d7a52
Revises: a74bf448a946
Create Date: 2026-11-02 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# 与 models 共用同一枚举对象：env.py 开了 compare_type=True，迁移里写裸 String
# 会被 alembic check 判成 modify_type 漂移（实测）；照抄 Enum(FaultPriority)，
# SQLite/PG 上渲染与建列行为同一致（同基线 status 列的处理口径）。
from app.models import FaultPriority


# revision identifiers, used by Alembic.
revision: str = 'b3e19c4d7a52'
down_revision: Union[str, Sequence[str], None] = 'a74bf448a946'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 增量变更（第二阶段：故障优先级）────────────────────────────
    # 需求三.2：旧库升级后"已有故障统一设为普通"，且不得清空/重录数据。
    # 手法：add_column 带 server_default='normal' —— SQLite 与 PG 都允许在
    # NOT NULL 加列时给默认值，存量行由数据库自动回填 'normal'，无需单独 UPDATE。
    # 列类型与基线风格一致：直接复用 models 的 Enum(FaultPriority)（在 SQLite/PG 上
    # 均渲染成 VARCHAR、无 CHECK 约束），避免与 compare_type 体检漂移。
    op.add_column(
        'pipeline_faults',
        sa.Column(
            'priority',
            sa.Enum(FaultPriority),
            nullable=False,
            server_default='normal',
        ),
    )
    # 回填完成后摘掉 server_default：与基线口径一致（Python 侧 default 不进 DDL，
    # 同 status 的 pending 默认值），避免绕过 ORM 的裸 SQL INSERT 静默吃掉库级默认值。
    # 【SQLite 坑】ALTER TABLE ... ALTER COLUMN ... DROP DEFAULT 是无效语法（实测报错），
    # 官方解法是 batch_alter_table：建临时表→拷数据→重命名，PG 上自动退化为普通 ALTER，
    # 同一份代码两方言都能跑（P3 已切双库支持，不能只保 SQLite）。
    with op.batch_alter_table('pipeline_faults') as batch_op:
        batch_op.alter_column('priority', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    # 回到无优先级列的结构：直接 DROP COLUMN（SQLite 3.35+ 支持，本机 Python 3.14
    # 自带的 sqlite3 远高于该版本；PG 原生支持）。优先级是展示维度，回滚丢列即可，
    # 不涉及数据修复 —— 与需求"升级不删数据"不冲突（回滚本身是人工决策操作）。
    op.drop_column('pipeline_faults', 'priority')
