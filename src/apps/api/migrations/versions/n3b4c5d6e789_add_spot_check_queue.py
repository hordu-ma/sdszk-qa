"""add spot check queue

Revision ID: n3b4c5d6e789
Revises: m2a3b4c5d678
Create Date: 2026-07-20 08:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n3b4c5d6e789"
down_revision: str | None = "m2a3b4c5d678"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spot_check_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("skill_run_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("sampled_by", sa.Integer(), nullable=False),
        sa.Column(
            "sample_source",
            sa.String(length=30),
            server_default="random_recent",
            nullable=False,
        ),
        sa.Column("skill_id", sa.String(length=100), nullable=False),
        sa.Column("skill_version", sa.String(length=30), nullable=False),
        sa.Column(
            "status", sa.String(length=30), server_default="pending", nullable=False
        ),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("resolved_verdict", sa.String(length=30), nullable=True),
        sa.Column("resolved_issue_tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["skill_run_id"], ["skill_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["teaching_projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sampled_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_run_id", name="uq_spot_check_items_skill_run_id"),
    )
    op.create_index("ix_spot_check_items_skill_run_id", "spot_check_items", ["skill_run_id"])
    op.create_index("ix_spot_check_items_project_id", "spot_check_items", ["project_id"])
    op.create_index("ix_spot_check_items_sampled_by", "spot_check_items", ["sampled_by"])
    op.create_index("ix_spot_check_items_skill_id", "spot_check_items", ["skill_id"])
    op.create_index("ix_spot_check_items_status", "spot_check_items", ["status"])
    op.create_table(
        "spot_check_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("review_kind", sa.String(length=30), nullable=False),
        sa.Column("verdict", sa.String(length=30), nullable=False),
        sa.Column("issue_tags", sa.JSON(), nullable=False),
        sa.Column("rubric_feedback", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["spot_check_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "item_id",
            "reviewer_id",
            "review_kind",
            name="uq_spot_check_reviewer_kind",
        ),
    )
    op.create_index("ix_spot_check_reviews_item_id", "spot_check_reviews", ["item_id"])
    op.create_index(
        "ix_spot_check_reviews_reviewer_id", "spot_check_reviews", ["reviewer_id"]
    )
    op.create_index(
        "ix_spot_check_reviews_review_kind", "spot_check_reviews", ["review_kind"]
    )


def downgrade() -> None:
    op.drop_index("ix_spot_check_reviews_review_kind", table_name="spot_check_reviews")
    op.drop_index("ix_spot_check_reviews_reviewer_id", table_name="spot_check_reviews")
    op.drop_index("ix_spot_check_reviews_item_id", table_name="spot_check_reviews")
    op.drop_table("spot_check_reviews")
    op.drop_index("ix_spot_check_items_status", table_name="spot_check_items")
    op.drop_index("ix_spot_check_items_skill_id", table_name="spot_check_items")
    op.drop_index("ix_spot_check_items_sampled_by", table_name="spot_check_items")
    op.drop_index("ix_spot_check_items_project_id", table_name="spot_check_items")
    op.drop_index("ix_spot_check_items_skill_run_id", table_name="spot_check_items")
    op.drop_table("spot_check_items")
