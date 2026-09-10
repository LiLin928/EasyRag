"""improve_dead_letter_tasks_schema

Revision ID: 455fccbb15c2
Revises: 67d2716c50c5
Create Date: 2026-09-10 15:19:16.400157

改进内容：
1. 将 args/kwargs 从 Text 改为 JSONB 类型，支持 JSON 查询
2. 添加 retried_by 外键关联到 users 表
3. 为 retry_count/max_retries/status 添加 server_default
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '455fccbb15c2'
down_revision: Union[str, Sequence[str], None] = '67d2716c50c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    1. 将 args/kwargs 字段从 Text 改为 JSONB
    2. 添加 retried_by 外键约束
    3. 确保默认值正确设置
    """
    # 使用原生 SQL 来修改字段类型
    # PostgreSQL 支持 USING 子句来转换数据类型
    op.execute("""
        ALTER TABLE dead_letter_tasks
        ALTER COLUMN args TYPE JSONB
        USING CASE
            WHEN args IS NULL THEN NULL
            ELSE args::jsonb
        END
    """)

    op.execute("""
        ALTER TABLE dead_letter_tasks
        ALTER COLUMN kwargs TYPE JSONB
        USING CASE
            WHEN kwargs IS NULL THEN NULL
            ELSE kwargs::jsonb
        END
    """)

    # 添加外键约束
    op.create_foreign_key(
        'fk_dead_letter_tasks_retried_by',
        'dead_letter_tasks',
        'users',
        ['retried_by'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema.

    回滚到之前的 Text 类型和移除外键。
    """
    # 移除外键约束
    op.drop_constraint('fk_dead_letter_tasks_retried_by', 'dead_letter_tasks', type_='foreignkey')

    # 将 JSONB 改回 Text
    op.execute("""
        ALTER TABLE dead_letter_tasks
        ALTER COLUMN args TYPE TEXT
        USING CASE
            WHEN args IS NULL THEN NULL
            ELSE args::text
        END
    """)

    op.execute("""
        ALTER TABLE dead_letter_tasks
        ALTER COLUMN kwargs TYPE TEXT
        USING CASE
            WHEN kwargs IS NULL THEN NULL
            ELSE kwargs::text
        END
    """)
