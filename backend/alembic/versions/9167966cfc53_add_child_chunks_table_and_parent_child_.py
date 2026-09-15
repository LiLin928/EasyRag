"""add child_chunks table and parent child fields

Revision ID: 9167966cfc53
Revises: 243058094b0b
Create Date: 2026-09-15 15:06:22.919950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9167966cfc53'
down_revision: Union[str, Sequence[str], None] = '243058094b0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 扩展 doc_tree_nodes 表
    op.add_column('doc_tree_nodes', sa.Column('parent_chunk_mode', sa.String(20), server_default='paragraph'))
    op.add_column('doc_tree_nodes', sa.Column('child_chunk_count', sa.Integer(), server_default='0'))
    op.add_column('doc_tree_nodes', sa.Column('parent_content', sa.Text(), nullable=True))

    # 2. 创建 child_chunks 表（不包含向量列）
    op.create_table(
        'child_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tree_node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kb_id', sa.String(36), nullable=False),
        sa.Column('position', sa.Integer(), server_default='1'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_search', sa.Text(), nullable=True),
        sa.Column('char_count', sa.Integer(), server_default='0'),
        sa.Column('embedding_model', sa.String(64), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}'),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tree_node_id'], ['doc_tree_nodes.id'], ondelete='CASCADE'),
    )

    # 3. 添加向量列（使用 pgvector 的 vector 类型）
    op.execute("""
        ALTER TABLE child_chunks
        ADD COLUMN embedding vector(1024);
    """)

    # 4. 创建索引
    op.create_index('idx_child_chunks_document', 'child_chunks', ['document_id'])
    op.create_index('idx_child_chunks_tree_node', 'child_chunks', ['tree_node_id'])
    op.create_index('idx_child_chunks_kb', 'child_chunks', ['kb_id'])

    # 5. 创建向量索引（使用 pgvector 的 ivfflat）
    op.execute("""
        CREATE INDEX idx_child_chunks_embedding
        ON child_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)

    # 6. 创建全文检索索引（pg_trgm）
    op.execute("""
        CREATE INDEX idx_child_chunks_content_search
        ON child_chunks
        USING gin (content_search gin_trgm_ops);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # 删除索引
    op.execute("DROP INDEX IF EXISTS idx_child_chunks_content_search")
    op.execute("DROP INDEX IF EXISTS idx_child_chunks_embedding")
    op.drop_index('idx_child_chunks_kb', 'child_chunks')
    op.drop_index('idx_child_chunks_tree_node', 'child_chunks')
    op.drop_index('idx_child_chunks_document', 'child_chunks')

    # 删除表
    op.drop_table('child_chunks')

    # 删除扩展字段
    op.drop_column('doc_tree_nodes', 'parent_content')
    op.drop_column('doc_tree_nodes', 'child_chunk_count')
    op.drop_column('doc_tree_nodes', 'parent_chunk_mode')
