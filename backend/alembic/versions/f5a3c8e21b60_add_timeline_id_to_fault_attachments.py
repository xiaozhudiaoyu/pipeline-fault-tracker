"""add timeline_id to fault_attachments (时间线附图)

Revision ID: f5a3c8e21b60
Revises: d8c2f5a91b47
Create Date: 2026-11-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a3c8e21b60'
down_revision: Union[str, Sequence[str], None] = 'd8c2f5a91b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 增量变更（第四阶段追加：进展/提交时间线可附图）──────────────────
    # fault_attachments 加一列可空 timeline_id：现场图片留 NULL，时间线附图指向
    # fault_timelines 行。batch_alter_table 包裹以兼容 SQLite（无原生 ALTER ADD
    # CONSTRAINT，走「建新表迁移数据」路径）；PG 下 batch 会退化为普通 ALTER。
    # 可空 + 无默认：既有附件（现场图片）全部按 NULL 归位，无回填。ondelete=CASCADE
    # 与 fault_id 方向一致（删故障连带清行），但时间线本身 append-only 不单独删。
    with op.batch_alter_table('fault_attachments') as batch_op:
        batch_op.add_column(
            sa.Column('timeline_id', sa.Integer(), nullable=True,
                      comment='关联时间线 ID（进展/提交附图），现场图片为 NULL')
        )
        # 时间线列表按 timeline_id 批量取附图（FaultTimeline.attachments selectinload 的 IN 查询）吃这个索引。
        batch_op.create_index('ix_fault_attachments_timeline_id', ['timeline_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_fault_attachments_timeline_id', 'fault_timelines',
            ['timeline_id'], ['id'], ondelete='CASCADE',
        )


def downgrade() -> None:
    """Downgrade schema."""
    # 结构可完整回退：删索引 + 删外键 + 删列（batch 重建表，SQLite/PG 同一路径）。
    # 【已知代价】同 add_fault_attachments：磁盘 uploads 下图片文件不在迁移管辖，
    # 回退后时间线附图行消失但文件仍在，成孤儿，不自动 rm（规则 2.6），人工核对后清理。
    with op.batch_alter_table('fault_attachments') as batch_op:
        batch_op.drop_index('ix_fault_attachments_timeline_id')
        batch_op.drop_constraint('fk_fault_attachments_timeline_id', type_='foreignkey')
        batch_op.drop_column('timeline_id')
