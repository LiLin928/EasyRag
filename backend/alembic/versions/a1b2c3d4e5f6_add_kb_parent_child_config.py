"""add kb parent-child config columns

Revision ID: a1b2c3d4e5f6
Revises: 9167966cfc53
Create Date: 2026-09-15 16:00:00.000000

知识库级别父子分段配置（方案§9）：
- retrieval_mode: 检索模式 traditional / parent_child
- child_chunk_size: 子分段目标大小
- child_chunk_overlap: 子分段重叠字符数
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9167966cfc53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: 给 knowledge_bases 表增加父子分段配置三列。"""
    op.add_column(
        'knowledge_bases',
        sa.Column(
            'retrieval_mode',
            sa.String(20),
            nullable=False,
            server_default='traditional',
            comment='检索模式：traditional(传统单层) / parent_child(父子分段)',
        ),
    )
    op.add_column(
        'knowledge_bases',
        sa.Column(
            'child_chunk_size',
            sa.Integer(),
            nullable=False,
            server_default='200',
            comment='父子分段模式下子分段目标大小（字符数）',
        ),
    )
    op.add_column(
        'knowledge_bases',
        sa.Column(
            'child_chunk_overlap',
            sa.Integer(),
            nullable=False,
            server_default='50',
            comment='父子分段模式下子分段重叠字符数',
        ),
    )


def downgrade() -> None:
    """Downgrade schema: 移除父子分段配置三列。"""
    op.drop_column('knowledge_bases', 'child_chunk_overlap')
    op.drop_column('knowledge_bases', 'child_chunk_size')
    op.drop_column('knowledge_bases', 'retrieval_mode')
