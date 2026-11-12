"""phase3_add_users_timelines_and_fault_columns

Revision ID: 105a10b2f697
Revises: b3e19c4d7a52
Create Date: 2026-11-03 09:33:59.571315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models import FaultStatus, FaultRole, TimelineAction


# revision identifiers, used by Alembic.
revision: str = '105a10b2f697'
down_revision: Union[str, Sequence[str], None] = 'b3e19c4d7a52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: 新增 users/fault_timelines 表 + pipeline_faults 加创建人/负责人列。

    设计要点（第三阶段需求二/四/六）：
      · users 表存储账号、角色、状态、token_version；
      · fault_timelines 表 append-only 记录处理过程，外键关联故障和用户；
      · pipeline_faults 加 created_by_id/assignee_id（可空，旧数据无对应账号）；
      · status 列不加 alter_column：SQLite 上 VARCHAR 不强制长度，新枚举值
        'awaiting_confirmation'(23字) 存入既有 VARCHAR(10) 完全没问题（基线已证实）；
        ORM 层 sa.Enum(FaultStatus) 负责应用级校验，数据库层无 CHECK 约束。
    """
    # ── 0. 方言开关：布尔列的 server_default 写法 ──────────────────────
    # 【PG 坑】sa.text('1')/'0' 在 SQLite 上能用（布尔存 0/1），但 PG 报
    # DatatypeMismatch: column is of type boolean but default is integer（实测）。
    # PG 渲染成布尔字面量 true/false，SQLite 保持原有 1/0 写法不变。
    _pg = op.get_bind().dialect.name == "postgresql"

    # ── 1. 新建 users 表 ──
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='用户主键'),
        sa.Column('username', sa.String(length=50), nullable=False, comment='登录用户名，全表唯一'),
        sa.Column('password_hash', sa.String(length=200), nullable=False, comment='bcrypt 哈希值，不保存明文'),
        sa.Column('display_name', sa.String(length=100), nullable=False, comment='显示名称'),
        sa.Column('role', sa.Enum(FaultRole), nullable=False, comment='角色：user/handler/admin'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true') if _pg else sa.text('1'), comment='账号启用状态'),
        sa.Column('token_version', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='token 版本号'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='账号创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )

    # ── 2. 新建 fault_timelines 表 ──
    op.create_table('fault_timelines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='时间线记录主键'),
        sa.Column('fault_id', sa.Integer(), nullable=False, comment='关联故障 ID'),
        sa.Column('action', sa.Enum(TimelineAction), nullable=False, comment='动作类型'),
        sa.Column('operator_id', sa.Integer(), nullable=True, comment='操作人用户 ID'),
        sa.Column('operator_name_snapshot', sa.String(length=100), nullable=True, comment='操作人名称快照'),
        sa.Column('from_status', sa.String(length=30), nullable=True, comment='变更前状态'),
        sa.Column('to_status', sa.String(length=30), nullable=True, comment='变更后状态'),
        sa.Column('from_assignee_id', sa.Integer(), nullable=True, comment='变更前负责人 ID'),
        sa.Column('to_assignee_id', sa.Integer(), nullable=True, comment='变更后负责人 ID'),
        sa.Column('note', sa.Text(), nullable=True, comment='说明/原因/进展内容'),
        sa.Column('is_imported', sa.Boolean(), nullable=False, server_default=sa.text('false') if _pg else sa.text('0'), comment='升级时导入标记'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='记录创建时间'),
        sa.ForeignKeyConstraint(['fault_id'], ['pipeline_faults.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['from_assignee_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_assignee_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_fault_timelines_fault_id'), 'fault_timelines', ['fault_id'], unique=False)

    # ── 3. pipeline_faults 加列 + 外键（batch 模式，SQLite 兼容）──
    # SQLite 不支持对已有表直接 ADD CONSTRAINT，用 batch_alter_table 绕开（同 priority 迁移手法）。
    with op.batch_alter_table('pipeline_faults') as batch_op:
        batch_op.add_column(sa.Column('created_by_id', sa.Integer(), nullable=True, comment='创建人用户 ID'))
        batch_op.add_column(sa.Column('assignee_id', sa.Integer(), nullable=True, comment='当前负责人用户 ID'))
        batch_op.create_foreign_key('fk_faults_created_by', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_faults_assignee', 'users', ['assignee_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade: 删除新增表与列，回到第二阶段结构。"""
    # 先删 pipeline_faults 新增列（FK 随列消失，SQLite 3.35+ 支持 DROP COLUMN）
    with op.batch_alter_table('pipeline_faults') as batch_op:
        batch_op.drop_constraint('fk_faults_assignee', type_='foreignkey')
        batch_op.drop_constraint('fk_faults_created_by', type_='foreignkey')
        batch_op.drop_column('assignee_id')
        batch_op.drop_column('created_by_id')
    # 再删时间线表和索引
    op.drop_index(op.f('ix_fault_timelines_fault_id'), table_name='fault_timelines')
    op.drop_table('fault_timelines')
    # 最后删用户表（被其他表 FK 引用，须后删）
    op.drop_table('users')
