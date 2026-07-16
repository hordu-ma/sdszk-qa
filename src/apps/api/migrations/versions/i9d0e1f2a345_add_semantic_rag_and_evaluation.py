"""add semantic rag and versioned evaluation

Revision ID: i9d0e1f2a345
Revises: h8c9d0e1f234
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "i9d0e1f2a345"
down_revision: str | Sequence[str] | None = "h8c9d0e1f234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "model_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=30), nullable=False),
        sa.Column("logical_name", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("repository", sa.String(length=255), nullable=False),
        sa.Column("revision", sa.String(length=64), nullable=False),
        sa.Column("served_model_name", sa.String(length=120), nullable=False),
        sa.Column("runtime", sa.String(length=30), nullable=False),
        sa.Column("runtime_version", sa.String(length=30), nullable=False),
        sa.Column("runtime_image", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("asset_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_type",
            "logical_name",
            "revision",
            "runtime_version",
            name="uq_model_asset_identity",
        ),
    )
    op.create_index("ix_model_assets_asset_type", "model_assets", ["asset_type"])
    op.create_index("ix_model_assets_logical_name", "model_assets", ["logical_name"])
    op.create_index("ix_model_assets_status", "model_assets", ["status"])

    op.create_table(
        "knowledge_index_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_revision", sa.String(length=64), nullable=False),
        sa.Column("reranker_model", sa.String(length=255), nullable=False),
        sa.Column("reranker_revision", sa.String(length=64), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["teaching_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "version_number", name="uq_knowledge_index_version"
        ),
    )
    op.create_index(
        "ix_knowledge_index_versions_project_id", "knowledge_index_versions", ["project_id"]
    )
    op.create_index(
        "ix_knowledge_index_versions_status", "knowledge_index_versions", ["status"]
    )
    op.create_index(
        "ix_knowledge_index_versions_config_hash", "knowledge_index_versions", ["config_hash"]
    )

    op.add_column(
        "knowledge_chunks", sa.Column("index_version_id", sa.Integer(), nullable=True)
    )
    op.add_column("knowledge_chunks", sa.Column("embedding", Vector(dim=512), nullable=True))
    op.add_column(
        "knowledge_chunks", sa.Column("embedding_model", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "knowledge_chunks", sa.Column("embedding_revision", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "knowledge_chunks", sa.Column("semantic_indexed_at", sa.DateTime(), nullable=True)
    )
    op.create_foreign_key(
        "fk_knowledge_chunks_index_version_id_knowledge_index_versions",
        "knowledge_chunks",
        "knowledge_index_versions",
        ["index_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_knowledge_chunks_index_version_id", "knowledge_chunks", ["index_version_id"]
    )
    op.create_index(
        "ix_knowledge_chunks_embedding_hnsw",
        "knowledge_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "evaluation_datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("dataset_key", sa.String(length=100), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["teaching_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "dataset_key", "version_number", name="uq_eval_dataset_version"
        ),
    )
    op.create_index("ix_evaluation_datasets_project_id", "evaluation_datasets", ["project_id"])
    op.create_index("ix_evaluation_datasets_owner_id", "evaluation_datasets", ["owner_id"])
    op.create_index("ix_evaluation_datasets_dataset_key", "evaluation_datasets", ["dataset_key"])
    op.create_index("ix_evaluation_datasets_status", "evaluation_datasets", ["status"])

    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("case_key", sa.String(length=100), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("expected_document_ids", sa.JSON(), nullable=False),
        sa.Column("expected_insufficient_basis", sa.Boolean(), nullable=False),
        sa.Column("case_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["evaluation_datasets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "case_key", name="uq_eval_case_key"),
    )
    op.create_index("ix_evaluation_cases_dataset_id", "evaluation_cases", ["dataset_id"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("release_manifest", sa.JSON(), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("matched_cases", sa.Integer(), nullable=False),
        sa.Column("failed_cases", sa.Integer(), nullable=False),
        sa.Column("error_cases", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["evaluation_datasets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_dataset_id", "evaluation_runs", ["dataset_id"])
    op.create_index("ix_evaluation_runs_user_id", "evaluation_runs", ["user_id"])
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])

    op.create_table(
        "evaluation_case_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("returned_document_ids", sa.JSON(), nullable=False),
        sa.Column("insufficient_basis", sa.Boolean(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["evaluation_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "case_id", name="uq_eval_run_case"),
    )
    op.create_index(
        "ix_evaluation_case_results_run_id", "evaluation_case_results", ["run_id"]
    )
    op.create_index(
        "ix_evaluation_case_results_case_id", "evaluation_case_results", ["case_id"]
    )
    op.create_index(
        "ix_evaluation_case_results_status", "evaluation_case_results", ["status"]
    )


def downgrade() -> None:
    op.drop_table("evaluation_case_results")
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_cases")
    op.drop_table("evaluation_datasets")

    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_index_version_id", table_name="knowledge_chunks")
    op.drop_constraint(
        "fk_knowledge_chunks_index_version_id_knowledge_index_versions",
        "knowledge_chunks",
        type_="foreignkey",
    )
    op.drop_column("knowledge_chunks", "semantic_indexed_at")
    op.drop_column("knowledge_chunks", "embedding_revision")
    op.drop_column("knowledge_chunks", "embedding_model")
    op.drop_column("knowledge_chunks", "embedding")
    op.drop_column("knowledge_chunks", "index_version_id")
    op.drop_table("knowledge_index_versions")
    op.drop_table("model_assets")
    # vector 扩展可能被同库其他对象共享，降级不自动删除。
