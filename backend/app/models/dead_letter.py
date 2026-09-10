"""死信任务 ORM 模型。

dead_letter_tasks 表存储超过最大重试次数的失败任务，
支持手动重试和统计分析。
"""
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk


class TaskStatus(str, Enum):
    """死信任务状态枚举。

    提供类型安全的状态值，避免硬编码字符串。

    Attributes:
        PENDING: 等待处理。
        RETRIED: 已重试。
        IGNORED: 已忽略。
    """
    PENDING = "pending"
    RETRIED = "retried"
    IGNORED = "ignored"


class DeadLetterTaskModel(Base, UUIDPk):
    """死信任务持久化模型。

    存储超过最大重试次数的失败任务，支持手动重试和统计分析。

    Attributes:
        task_id: Celery 任务 ID，唯一标识。
        task_name: 任务名称，如 "parse_document"。
        args: 任务位置参数，JSONB 格式支持查询。
        kwargs: 任务关键字参数，JSONB 格式支持查询。
        exception: 异常信息字符串。
        traceback: 堆栈跟踪字符串。
        retry_count: 重试次数，默认 0。
        max_retries: 最大重试次数，默认 3。
        status: 任务状态，使用 TaskStatus 枚举。
        created_at: 创建时间，默认为入库时数据库当前时间。
        retried_at: 重试时间（可空）。
        retried_by: 重试操作用户 ID（可空），关联 users 表。
    """

    __tablename__ = "dead_letter_tasks"

    task_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    args: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    kwargs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exception: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    status: Mapped[str] = mapped_column(
        String(20), default=TaskStatus.PENDING.value, index=True, server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    retried_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retried_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<DeadLetterTask {self.task_name}[{self.task_id}]>"