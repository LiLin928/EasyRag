"""KB metadata and retrieval testing schema

Revision ID: b71d0c8f4aa2
Revises: 71dc230762db
Create Date: 2026-08-17 22:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b71d0c8f4aa2"
down_revision = "71dc230762db"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_bases",
        sa.Column("embedding_model_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("rerank_model_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "retrieval_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_foreign_key(
        "knowledge_bases_embedding_model_id_fkey",
        "knowledge_bases",
        "model_configs",
        ["embedding_model_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "knowledge_bases_rerank_model_id_fkey",
        "knowledge_bases",
        "model_configs",
        ["rerank_model_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "documents",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "recall_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "chunks",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "recall_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "char_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_table(
        "kb_metadata_fields",
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "filterable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "retrieval_filterable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "built_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("mapped_field", sa.String(length=64), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["kb_id"],
            ["knowledge_bases.id"],
            name="kb_metadata_fields_kb_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "kb_id",
            "scope",
            "key",
            name="uq_kb_metadata_scope_key",
        ),
    )
    op.create_index(
        "ix_kb_metadata_fields_kb_id",
        "kb_metadata_fields",
        ["kb_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO kb_metadata_fields (
            id, kb_id, key, name, scope, data_type, visible, built_in,
            mapped_field, sort_order, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            kb.id,
            seed.key,
            seed.name,
            'document',
            seed.data_type,
            true,
            true,
            seed.mapped_field,
            seed.sort_order,
            now(),
            now()
        FROM knowledge_bases AS kb
        CROSS JOIN (
            VALUES
                ('document_name', 'document_name', 'string', 'name', 0),
                ('file_size', 'file_size', 'number', 'size', 1),
                ('uploader', 'uploader', 'string', 'user_id', 2),
                ('upload_date', 'upload_date', 'date', 'created_at', 3),
                ('last_update_date', 'last_update_date', 'date', 'updated_at', 4),
                ('source', 'source', 'string', NULL, 5)
        ) AS seed(key, name, data_type, mapped_field, sort_order)
        WHERE NOT EXISTS (
            SELECT 1
            FROM kb_metadata_fields AS existing
            WHERE existing.kb_id = kb.id
              AND existing.scope = 'document'
              AND existing.key = seed.key
        )
        """
    )

    op.create_table(
        "retrieval_test_sets",
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["kb_id"],
            ["knowledge_bases.id"],
            name="retrieval_test_sets_kb_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieval_test_sets_kb_id",
        "retrieval_test_sets",
        ["kb_id"],
        unique=False,
    )

    op.create_table(
        "retrieval_test_cases",
        sa.Column("test_set_id", sa.UUID(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column(
            "expected_doc_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "expected_chunk_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["test_set_id"],
            ["retrieval_test_sets.id"],
            name="retrieval_test_cases_test_set_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieval_test_cases_test_set_id",
        "retrieval_test_cases",
        ["test_set_id"],
        unique=False,
    )

    op.create_table(
        "retrieval_test_runs",
        sa.Column("test_set_id", sa.UUID(), nullable=False),
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "config_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "override_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "total_cases",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "completed_cases",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["test_set_id"],
            ["retrieval_test_sets.id"],
            name="retrieval_test_runs_test_set_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["kb_id"],
            ["knowledge_bases.id"],
            name="retrieval_test_runs_kb_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieval_test_runs_test_set_id",
        "retrieval_test_runs",
        ["test_set_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_test_runs_kb_id",
        "retrieval_test_runs",
        ["kb_id"],
        unique=False,
    )
    op.create_index(
        "uq_retrieval_test_runs_active",
        "retrieval_test_runs",
        ["test_set_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "retrieval_test_case_results",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "expected_doc_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "hit_doc_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["retrieval_test_runs.id"],
            name="retrieval_test_case_results_run_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["retrieval_test_cases.id"],
            name="retrieval_test_case_results_case_id_fkey",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieval_test_case_results_run_id",
        "retrieval_test_case_results",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_test_case_results_case_id",
        "retrieval_test_case_results",
        ["case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_retrieval_test_case_results_case_id",
        table_name="retrieval_test_case_results",
    )
    op.drop_index(
        "ix_retrieval_test_case_results_run_id",
        table_name="retrieval_test_case_results",
    )
    op.drop_table("retrieval_test_case_results")
    op.drop_index("uq_retrieval_test_runs_active", table_name="retrieval_test_runs")
    op.drop_index("ix_retrieval_test_runs_kb_id", table_name="retrieval_test_runs")
    op.drop_index(
        "ix_retrieval_test_runs_test_set_id",
        table_name="retrieval_test_runs",
    )
    op.drop_table("retrieval_test_runs")
    op.drop_index(
        "ix_retrieval_test_cases_test_set_id",
        table_name="retrieval_test_cases",
    )
    op.drop_table("retrieval_test_cases")
    op.drop_index("ix_retrieval_test_sets_kb_id", table_name="retrieval_test_sets")
    op.drop_table("retrieval_test_sets")
    op.drop_index("ix_kb_metadata_fields_kb_id", table_name="kb_metadata_fields")
    op.drop_table("kb_metadata_fields")

    op.drop_column("chunks", "char_count")
    op.drop_column("chunks", "recall_count")
    op.drop_column("chunks", "enabled")
    op.drop_column("chunks", "metadata")
    op.drop_column("documents", "recall_count")
    op.drop_column("documents", "enabled")
    op.drop_column("documents", "metadata")
    op.drop_constraint(
        "knowledge_bases_rerank_model_id_fkey",
        "knowledge_bases",
        type_="foreignkey",
    )
    op.drop_constraint(
        "knowledge_bases_embedding_model_id_fkey",
        "knowledge_bases",
        type_="foreignkey",
    )
    op.drop_column("knowledge_bases", "retrieval_config")
    op.drop_column("knowledge_bases", "rerank_model_id")
    op.drop_column("knowledge_bases", "embedding_model_id")
