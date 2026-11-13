"""add fault_attachments (图片附件元数据表)

Revision ID: d8c2f5a91b47
Revises: 105a10b2f697
Create Date: 2026-11-13 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8c2f5a91b47'
down_revision: Union[str, Sequence[str], None] = '105a10b2f697'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 增量变更（第四阶段：图片附件）────────────────────────────
    # 库内只存元数据行，文件本体在 settings.upload_dir（容器形态落 pft-data 卷）。
    # 全新空表，无存量数据回填；列类型全部为 Integer/String/DateTime 基础类型，
    # 不含 Enum（SQLite 渲染 VARCHAR、PG 原生类型两可的坑本表天然规避），
    # 双方言同一份 DDL 直接可跑。
    op.create_table(
        'fault_attachments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='附件主键'),
        sa.Column('fault_id', sa.Integer(), nullable=False, comment='关联故障 ID'),
        sa.Column('filename', sa.String(length=64), nullable=False, comment='服务端重写后的存储文件名（uuid4().hex + 扩展名），upload_dir 下的相对文件名'),
        sa.Column('original_name', sa.String(length=255), nullable=False, comment='客户端上传时的原始文件名，仅展示用，不参与任何路径拼接'),
        sa.Column('content_type', sa.String(length=50), nullable=False, comment='服务端 magic bytes 判定的真实 MIME：image/png 或 image/jpeg'),
        sa.Column('size_bytes', sa.Integer(), nullable=False, comment='文件字节数（落盘后实测值）'),
        sa.Column('uploader_id', sa.Integer(), nullable=True, comment='上传人用户 ID，可空（账号被删后保留快照）'),
        sa.Column('uploader_name_snapshot', sa.String(length=100), nullable=True, comment='上传人显示名快照（口径同 timeline.operator_name_snapshot）'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='上传时间（ORM 侧走 _local_now，本默认仅供绕过 ORM 的裸 SQL 兑底，口径同基线）'),
        sa.ForeignKeyConstraint(['fault_id'], ['pipeline_faults.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploader_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    # 列表页按 fault_id 批量取附件（selectinload 的 IN 查询）与回放端点权限回溯都吃这个索引，
    # 索引名与 ORM 侧 create_index 自动命名保持一致（alembic check 体检项）。
    op.create_index(op.f('ix_fault_attachments_fault_id'), 'fault_attachments', ['fault_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 结构可完整回退：删索引 + 删元数据表即可（无其他表引用本表，FK 方向都是出边）。
    # 【已知代价】磁盘 uploads 目录下的图片文件不在本迁移管辖内：downgrade 后它们
    # 变成无元数据指向的孤儿文件，仍占 pft-data 卷空间。不自动 rm -rf（规则 2.6：
    # 删数据须人工决策），需要清理时人工核对目录后删除。
    op.drop_index(op.f('ix_fault_attachments_fault_id'), table_name='fault_attachments')
    op.drop_table('fault_attachments')
