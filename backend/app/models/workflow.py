"""工作流 ORM 模型。

5 张表：workflows / workflow_versions / workflow_executions /
workflow_todos / workflow_templates，覆盖工作流定义、版本、执行、待办、模板。
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPk


class Workflow(Base, UUIDPk, TimestampMixin):
    """工作流定义表。"""

    __tablename__ = "workflows"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft / published / archived
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    definition: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # {nodes, edges, global_variables}
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_run: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    webhook_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)


class WorkflowVersion(Base, UUIDPk, TimestampMixin):
    """工作流版本快照表。"""

    __tablename__ = "workflow_versions"
    __table_args__ = (UniqueConstraint("workflow_id", "version", name="uq_wfver_wf_version"),)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class WorkflowExecution(Base, UUIDPk):
    """工作流执行记录表。"""

    __tablename__ = "workflow_executions"
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/paused/completed/failed/cancelled
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual")  # manual/api/webhook/chat/agent
    inputs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    outputs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    node_progress: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # "4/7"
    detail_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class WorkflowTodo(Base, UUIDPk):
    """工作流人工待办表。"""

    __tablename__ = "workflow_todos"
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_executions.id", ondelete="CASCADE"), index=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # "流程 · 节点"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    form_schema: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # FormField[]
    form_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/done/rejected/timeout
    deadline: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class WorkflowTemplate(Base, UUIDPk):
    """工作流模板表。"""

    __tablename__ = "workflow_templates"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="official")  # official / community
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    thumbnail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {nodes, edges}
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
