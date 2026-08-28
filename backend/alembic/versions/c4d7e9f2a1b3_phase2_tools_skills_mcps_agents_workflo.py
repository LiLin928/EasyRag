"""phase2: tools, skills, mcps, agents, workflows, versions, executions, todos, templates

Revision ID: c4d7e9f2a1b3
Revises: a3f2c8e1b9d4
Create Date: 2026-08-28 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4d7e9f2a1b3"
down_revision = "a3f2c8e1b9d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- tools --
    op.create_table(
        "tools",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="HTTP"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sig", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("params", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("auth", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # -- skills --
    op.create_table(
        "skills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=False, server_default="🔧"),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="custom"),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1.0.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("tools", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("docs", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("wfs", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("examples", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("scripts", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("budget", sa.Integer(), nullable=True),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # -- mcps --
    op.create_table(
        "mcps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("tp", sa.String(length=16), nullable=False, server_default="stdio"),
        sa.Column("cmd", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="off"),
        sa.Column("tool_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("env", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("timeout", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # -- agents --
    op.create_table(
        "agents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=False, server_default="gpt-4o"),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("temp", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("maxtok", sa.String(length=16), nullable=False, server_default="2048"),
        sa.Column("tools", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("docs", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("wfs", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("mcps", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skills", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_active", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # -- workflows --
    op.create_table(
        "workflows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("definition", postgresql.JSONB(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=True),
        sa.Column("last_run", sa.DateTime(), nullable=True),
        sa.Column("webhook_token", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("webhook_token", name="uq_workflows_webhook_token"),
    )
    op.create_index(op.f("ix_workflows_user_id"), "workflows", ["user_id"])

    # -- workflow_versions --
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("change_summary", postgresql.JSONB(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workflow_id", "version", name="uq_wfver_wf_version"),
    )
    op.create_index(op.f("ix_workflow_versions_workflow_id"), "workflow_versions", ["workflow_id"])

    # -- workflow_executions --
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("trigger_type", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("inputs", postgresql.JSONB(), nullable=True),
        sa.Column("outputs", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("node_progress", sa.String(length=32), nullable=True),
        sa.Column("detail_key", sa.String(length=200), nullable=True),
        sa.Column("trace_id", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_workflow_executions_workflow_id"), "workflow_executions", ["workflow_id"])
    op.create_index(op.f("ix_workflow_executions_status"), "workflow_executions", ["status"])
    op.create_index(op.f("ix_workflow_executions_user_id"), "workflow_executions", ["user_id"])

    # -- workflow_todos --
    op.create_table(
        "workflow_todos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("form_schema", postgresql.JSONB(), nullable=True),
        sa.Column("form_data", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["execution_id"], ["workflow_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_workflow_todos_execution_id"), "workflow_todos", ["execution_id"])
    op.create_index(op.f("ix_workflow_todos_workflow_id"), "workflow_todos", ["workflow_id"])
    op.create_index(op.f("ix_workflow_todos_status"), "workflow_todos", ["status"])

    # -- workflow_templates --
    op.create_table(
        "workflow_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="official"),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("thumbnail", sa.String(length=255), nullable=True),
        sa.Column("node_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_templates")
    op.drop_index(op.f("ix_workflow_todos_status"), table_name="workflow_todos")
    op.drop_index(op.f("ix_workflow_todos_workflow_id"), table_name="workflow_todos")
    op.drop_index(op.f("ix_workflow_todos_execution_id"), table_name="workflow_todos")
    op.drop_table("workflow_todos")
    op.drop_index(op.f("ix_workflow_executions_user_id"), table_name="workflow_executions")
    op.drop_index(op.f("ix_workflow_executions_status"), table_name="workflow_executions")
    op.drop_index(op.f("ix_workflow_executions_workflow_id"), table_name="workflow_executions")
    op.drop_table("workflow_executions")
    op.drop_index(op.f("ix_workflow_versions_workflow_id"), table_name="workflow_versions")
    op.drop_table("workflow_versions")
    op.drop_index(op.f("ix_workflows_user_id"), table_name="workflows")
    op.drop_table("workflows")
    op.drop_table("agents")
    op.drop_table("mcps")
    op.drop_table("skills")
    op.drop_table("tools")
