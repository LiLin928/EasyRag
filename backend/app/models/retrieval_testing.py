"""Retrieval testing ORM models."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk

RUN_STATUSES = {"pending", "running", "completed", "failed", "canceled"}
CASE_RESULT_STATUSES = {
    "pending",
    "running",
    "hit",
    "partial_hit",
    "miss",
    "failed",
    "skipped",
}


class RetrievalTestSet(Base, UUIDPk):
    """A reusable set of retrieval regression cases."""

    __tablename__ = "retrieval_test_sets"

    kb_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class RetrievalTestCase(Base, UUIDPk):
    """One query and its expected document identifiers."""

    __tablename__ = "retrieval_test_cases"

    test_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval_test_sets.id", ondelete="CASCADE"), index=True
    )
    query: Mapped[str] = mapped_column(Text)
    expected_doc_ids: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    expected_chunk_ids: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    tags: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class RetrievalTestRun(Base, UUIDPk):
    """One execution of a retrieval test set."""

    __tablename__ = "retrieval_test_runs"
    __table_args__ = (
        Index(
            "uq_retrieval_test_runs_active",
            "test_set_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    test_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval_test_sets.id"), index=True
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_bases.id"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    config_snapshot: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    override_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    total_cases: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completed_cases: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RetrievalTestCaseResult(Base, UUIDPk):
    """Persisted result for one case within a run."""

    __tablename__ = "retrieval_test_case_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("retrieval_test_runs.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("retrieval_test_cases.id", ondelete="SET NULL"), index=True
    )
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    expected_doc_ids: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    hit_doc_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    results: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
