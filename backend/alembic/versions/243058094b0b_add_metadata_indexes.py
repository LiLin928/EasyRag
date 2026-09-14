"""add_metadata_indexes

Revision ID: 243058094b0b
Revises: 17b2dd965edb
Create Date: 2026-09-14 16:42:26.728075

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '243058094b0b'
down_revision: Union[str, Sequence[str], None] = '17b2dd965edb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加元数据索引以优化检索性能。"""
    # GIN索引（通用元数据查询）
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_metadata_gin
        ON chunks USING GIN (metadata jsonb_path_ops)
    """)

    # 常用字段索引（根据实际需求调整）
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_metadata_department
        ON chunks USING BTREE ((metadata->>'department'))
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_metadata_status
        ON chunks USING BTREE ((metadata->>'status'))
    """)

    # 复合索引（kb_id + enabled）
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_kb_enabled
        ON chunks (kb_id, enabled)
        WHERE enabled = true
    """)


def downgrade() -> None:
    """回滚索引。"""
    op.execute("DROP INDEX IF EXISTS idx_chunks_metadata_gin")
    op.execute("DROP INDEX IF EXISTS idx_chunks_metadata_department")
    op.execute("DROP INDEX IF EXISTS idx_chunks_metadata_status")
    op.execute("DROP INDEX IF EXISTS idx_chunks_kb_enabled")
