"""add skills runtime, memory minimal set, and pg_trgm retrieval

Revision ID: f7b8c9d0e123
Revises: e6a7b8c9d012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b8c9d0e123"
down_revision: str | Sequence[str] | None = "e6a7b8c9d012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 库内可扩展检索依赖 pg_trgm（标准 contrib 扩展，无需额外镜像）
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "skill_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.String(length=100), nullable=False),
        sa.Column("skill_version", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("execution_mode", sa.String(length=10), nullable=False),
        sa.Column("maturity", sa.String(length=30), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("required_roles", sa.JSON(), nullable=False),
        sa.Column("quota_class", sa.String(length=30), nullable=False),
        sa.Column("timeout_ms", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("model_logic_name", sa.String(length=100), nullable=True),
        sa.Column("rule_set_version", sa.String(length=30), nullable=True),
        sa.Column("knowledge_scope", sa.String(length=100), nullable=True),
        sa.Column("degradation_policy", sa.String(length=100), nullable=True),
        sa.Column("audit_level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id"),
    )
    op.create_index("ix_skill_definitions_skill_id", "skill_definitions", ["skill_id"], unique=True)
    op.create_index("ix_skill_definitions_status", "skill_definitions", ["status"])

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("default_stage", sa.String(length=50), nullable=True),
        sa.Column("default_course_type", sa.String(length=50), nullable=True),
        sa.Column("textbook_version", sa.String(length=100), nullable=True),
        sa.Column("export_template", sa.String(length=100), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=True)

    op.create_table(
        "class_context_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_class_profile_user_name"),
    )
    op.create_index("ix_class_context_profiles_user_id", "class_context_profiles", ["user_id"])

    op.create_table(
        "memory_injection_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill_run_id", sa.Integer(), nullable=False),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("memory_id", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["skill_run_id"], ["skill_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_injection_audits_created_at", "memory_injection_audits", ["created_at"])
    op.create_index("ix_memory_injection_audits_skill_run_id", "memory_injection_audits", ["skill_run_id"])
    op.create_index("ix_memory_injection_audits_user_id", "memory_injection_audits", ["user_id"])

    op.add_column("skill_runs", sa.Column("input_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "skill_runs",
        sa.Column("memory_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column("skill_runs", sa.Column("error_code", sa.String(length=100), nullable=True))
    op.add_column("skill_runs", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("skill_runs", sa.Column("finished_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("skill_runs", "finished_at")
    op.drop_column("skill_runs", "started_at")
    op.drop_column("skill_runs", "error_code")
    op.drop_column("skill_runs", "memory_refs")
    op.drop_column("skill_runs", "input_hash")
    op.drop_table("memory_injection_audits")
    op.drop_table("class_context_profiles")
    op.drop_table("user_preferences")
    op.drop_table("skill_definitions")
