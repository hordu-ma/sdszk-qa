"""add evaluation gold reviews

Revision ID: k1f2a3b4c567
Revises: j0e1f2a3b456
Create Date: 2026-07-17 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k1f2a3b4c567"
down_revision: str | None = "j0e1f2a3b456"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_cases",
        sa.Column(
            "gold_status",
            sa.String(length=30),
            server_default="not_applicable",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_evaluation_cases_gold_status", "evaluation_cases", ["gold_status"]
    )
    op.execute(
        """
        UPDATE evaluation_cases AS evaluation_case
        SET gold_status = 'pending'
        FROM evaluation_datasets AS dataset
        WHERE evaluation_case.dataset_id = dataset.id
          AND dataset.data_origin <> 'synthetic'
        """
    )
    op.create_table(
        "evaluation_case_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("review_kind", sa.String(length=30), nullable=False),
        sa.Column("expected_document_ids", sa.JSON(), nullable=False),
        sa.Column("expected_insufficient_basis", sa.Boolean(), nullable=False),
        sa.Column("critical_error_tags", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"], ["evaluation_cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "case_id",
            "reviewer_id",
            "review_kind",
            name="uq_eval_case_reviewer_kind",
        ),
    )
    op.create_index(
        "ix_evaluation_case_reviews_case_id",
        "evaluation_case_reviews",
        ["case_id"],
    )
    op.create_index(
        "ix_evaluation_case_reviews_reviewer_id",
        "evaluation_case_reviews",
        ["reviewer_id"],
    )
    op.create_index(
        "ix_evaluation_case_reviews_review_kind",
        "evaluation_case_reviews",
        ["review_kind"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_case_reviews_review_kind",
        table_name="evaluation_case_reviews",
    )
    op.drop_index(
        "ix_evaluation_case_reviews_reviewer_id",
        table_name="evaluation_case_reviews",
    )
    op.drop_index(
        "ix_evaluation_case_reviews_case_id",
        table_name="evaluation_case_reviews",
    )
    op.drop_table("evaluation_case_reviews")
    op.drop_index("ix_evaluation_cases_gold_status", table_name="evaluation_cases")
    op.drop_column("evaluation_cases", "gold_status")
