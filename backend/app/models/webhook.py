\"\"\"Webhook触发器模型。\"\"\"
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Webhook(Base, UUIDPk, TimestampMixin):
    \"\"\"Webhook触发器表。\"\"\"
    __tablename__ = \"webhooks\"
    
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(\"workflows.id\", ondelete=\"CASCADE\"),
        index=True,
        nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(\"users.id\"),
        index=True,
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 触发条件过滤器
    filters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # 例如: {\"event_type\": \"document.created\", \"source\": \"api\"}
    
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    trigger_count: Mapped[int] = mapped_column(default=0)
    
    # 速率限制
    rate_limit_per_minute: Mapped[int] = mapped_column(default=60)


class WebhookTriggerLog(Base, UUIDPk):
    \"\"\"Webhook触发日志表。\"\"\"
    __tablename__ = \"webhook_trigger_logs\"
    
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(\"webhooks.id\", ondelete=\"CASCADE\"),
        index=True,
        nullable=False
    )
    workflow_execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(\"workflow_executions.id\", ondelete=\"SET NULL\"),
        nullable=True
    )
    
    # 触发详情
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    headers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # 验证结果
    signature_valid: Mapped[bool] = mapped_column(default=False)
    signature_version: Mapped[str] = mapped_column(String(10), default=\"v1\")
    
    # 执行结果
    status: Mapped[str] = mapped_column(
        String(20),
        default=\"pending\"
    )  # pending / running / completed / failed / filtered
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
