"""add_defaults_to_dead_letter_tasks

Revision ID: 46e0b3c1966b
Revises: 455fccbb15c2
Create Date: 2026-09-10 15:22:09.477784

为 dead_letter_tasks 表添加数据库层面的默认值。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46e0b3c1966b'
down_revision: Union[str, Sequence[str], None] = '455fccbb15c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    为 retry_count, max_retries, status 添加数据库层面的默认值。
    """
    op.alter_column('dead_letter_tasks', 'retry_count',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='0')
    op.alter_column('dead_letter_tasks', 'max_retries',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='3')
    op.alter_column('dead_letter_tasks', 'status',
                    existing_type=sa.String(length=20),
                    nullable=False,
                    server_default='pending')


def downgrade() -> None:
    """Downgrade schema.

    移除默认值（保留 NOT NULL 约束）。
    """
    op.alter_column('dead_letter_tasks', 'status',
                    existing_type=sa.String(length=20),
                    nullable=False,
                    server_default=None)
    op.alter_column('dead_letter_tasks', 'max_retries',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default=None)
    op.alter_column('dead_letter_tasks', 'retry_count',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default=None)
