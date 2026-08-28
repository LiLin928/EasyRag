"""Knowledge-base metadata field ORM model."""
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class KbMetadataField(Base, UUIDPk, TimestampMixin):
    """Configurable metadata field for document or chunk assets."""

    __tablename__ = "kb_metadata_fields"
    __table_args__ = (
        UniqueConstraint("kb_id", "scope", "key", name="uq_kb_metadata_scope_key"),
    )

    kb_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[str] = mapped_column(String(16))
    data_type: Mapped[str] = mapped_column(String(16))
    options: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    default_value: Mapped[dict | list | str | float | bool | None] = mapped_column(
        JSONB, nullable=True
    )
    required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    filterable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    retrieval_filterable: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    visible: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    built_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    mapped_field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
