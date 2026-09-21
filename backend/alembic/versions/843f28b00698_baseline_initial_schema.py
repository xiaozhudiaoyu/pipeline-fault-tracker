"""baseline initial schema

Revision ID: 843f28b00698
Revises: 
Create Date: 2026-09-20 17:25:55.988753

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '843f28b00698'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 手写基线（D2）──────────────────────────────────────────────
    # 本项目此前用 Base.metadata.create_all() 自动建表，引入 Alembic 时两张表
    # 早已存在于 fault_tracker.db。此时直接 autogenerate 对"已存在且与模型一致"
    # 的表不会产出任何 CREATE，基线将为空——换一台空库跑 upgrade head 就无法
    # 重建 schema，基线失去意义。
    #
    # 因此这里手写完整建表：列定义照抄现有库 sqlite_master 导出的真实 DDL
    # （2026-09-20 实测导出），按外键依赖顺序 create_table（先被引用的
    # pipelines，再引用它的 pipeline_faults）。现有库用 `alembic stamp` 打标记
    # （只写 alembic_version，不重跑下面的 CREATE），空库则能靠它从零重建——
    # 两种场景都成立。
    #
    # 与 models.py 的对应关系（照实抄录，不"补全"）：
    #   · status 是 Enum(FaultStatus) 渲染成的 VARCHAR(10)，无 CHECK 约束
    #     （SQLAlchemy Enum 默认 create_constraint=False），也无 DEFAULT——
    #     pending 是 Python 侧默认值，不进 DDL。
    #   · created_at/updated_at 的 DEFAULT CURRENT_TIMESTAMP 来自
    #     server_default=func.now()；updated_at 的 onupdate 是 ORM 层行为，不进 DDL。
    op.create_table(
        'pipelines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_table(
        'pipeline_faults',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pipeline_id', sa.Integer(), nullable=False),
        sa.Column('location', sa.String(length=200), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('symptom', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('handling_note', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['pipeline_id'], ['pipelines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 回滚顺序与 upgrade 相反：先删引用别人的 pipeline_faults，再删被引用的
    # pipelines。顺序反了会因外键仍存在而 DROP 失败。
    op.drop_table('pipeline_faults')
    op.drop_table('pipelines')
