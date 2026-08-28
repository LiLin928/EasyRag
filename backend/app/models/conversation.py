"""会话与消息 ORM 模型。"""
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Conversation(Base, UUIDPk, TimestampMixin):
    """会话表，多轮对话的容器。"""

    __tablename__ = "conversations"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kb_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_time: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    msg_count: Mapped[int] = mapped_column(Integer, default=0)


class Message(Base, UUIDPk, TimestampMixin):
    """消息表，对话中的单条消息。"""

    __tablename__ = "messages"
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    references: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    trace: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class Feedback(Base, UUIDPk, TimestampMixin):
    """用户反馈表。"""

    __tablename__ = "feedbacks"
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16))  # like / dislike
