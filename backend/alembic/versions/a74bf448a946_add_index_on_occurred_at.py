"""add index on occurred_at

Revision ID: a74bf448a946
Revises: 843f28b00698
Create Date: 2026-09-20 17:25:57.720241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a74bf448a946'
down_revision: Union[str, Sequence[str], None] = '843f28b00698'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 增量变更（D2）──────────────────────────────────────────────
    # GET /api/faults 按 occurred_at 倒序排序且支持时间范围筛选，是查询热点列，
    # 给它建普通索引加速排序/范围扫描。
    # 与 models.py 同步：occurred_at 加了 index=True，新库 create_all 会建同名
    # 索引 ix_pipeline_faults_occurred_at，模型与库两边不漂移。
    op.create_index('ix_pipeline_faults_occurred_at', 'pipeline_faults', ['occurred_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_pipeline_faults_occurred_at', table_name='pipeline_faults')
