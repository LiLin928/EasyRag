"""tree nodes and elements

Revision ID: 71dc230762db
Revises: f9a68189a76d
Create Date: 2026-08-09 15:07:44.494169
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = '71dc230762db'
down_revision = 'f9a68189a76d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('doc_tree_nodes',
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('parent_id', sa.UUID(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('element_count', sa.Integer(), nullable=False),
        sa.Column('page_start', sa.Integer(), nullable=True),
        sa.Column('page_end', sa.Integer(), nullable=True),
        sa.Column('nav_embedding', Vector(dim=1024), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['doc_tree_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_doc_tree_nodes_document_id'), 'doc_tree_nodes', ['document_id'], unique=False)
    op.create_table('element_positions',
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('chunk_id', sa.UUID(), nullable=True),
        sa.Column('tree_node_id', sa.UUID(), nullable=True),
        sa.Column('element_type', sa.String(length=20), nullable=False),
        sa.Column('element_index', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('image_key', sa.String(length=512), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['chunks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tree_node_id'], ['doc_tree_nodes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_element_positions_chunk_id'), 'element_positions', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_element_positions_document_id'), 'element_positions', ['document_id'], unique=False)
    op.create_index(op.f('ix_element_positions_tree_node_id'), 'element_positions', ['tree_node_id'], unique=False)
    # 手补：结构树父节点索引 + 导航向量索引
    op.execute("CREATE INDEX IF NOT EXISTS idx_tree_parent ON doc_tree_nodes (parent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tree_nav ON doc_tree_nodes USING ivfflat (nav_embedding vector_cosine_ops) WITH (lists = 50)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tree_nav")
    op.execute("DROP INDEX IF EXISTS idx_tree_parent")
    op.drop_index(op.f('ix_element_positions_tree_node_id'), table_name='element_positions')
    op.drop_index(op.f('ix_element_positions_document_id'), table_name='element_positions')
    op.drop_index(op.f('ix_element_positions_chunk_id'), table_name='element_positions')
    op.drop_table('element_positions')
    op.drop_index(op.f('ix_doc_tree_nodes_document_id'), table_name='doc_tree_nodes')
    op.drop_table('doc_tree_nodes')
