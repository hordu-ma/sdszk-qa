"""add vertical sample exports and pinned memory items

Revision ID: h8c9d0e1f234
Revises: f7b8c9d0e123
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h8c9d0e1f234"
down_revision: str | Sequence[str] | None = "f7b8c9d0e123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pinned_memory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=30), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["teaching_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_type", "name", name="uq_pinned_item_user_type_name"),
    )
    op.create_index("ix_pinned_memory_items_project_id", "pinned_memory_items", ["project_id"])
    op.create_index("ix_pinned_memory_items_user_id", "pinned_memory_items", ["user_id"])

    op.create_table(
        "artifact_exports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill_run_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("template_version", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["teaching_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_run_id"], ["skill_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["project_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_artifact_exports_created_at", "artifact_exports", ["created_at"])
    op.create_index("ix_artifact_exports_project_id", "artifact_exports", ["project_id"])
    op.create_index(
        "ix_artifact_exports_skill_run_id", "artifact_exports", ["skill_run_id"], unique=True
    )
    op.create_index("ix_artifact_exports_user_id", "artifact_exports", ["user_id"])
    op.create_index("ix_artifact_exports_version_id", "artifact_exports", ["version_id"])


def downgrade() -> None:
    op.drop_table("artifact_exports")
    op.drop_table("pinned_memory_items")
