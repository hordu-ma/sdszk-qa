"""label evaluation data origin and external review state

Revision ID: j0e1f2a3b456
Revises: i9d0e1f2a345
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j0e1f2a3b456"
down_revision: str | Sequence[str] | None = "i9d0e1f2a345"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_datasets",
        sa.Column(
            "data_origin",
            sa.String(length=30),
            server_default="synthetic",
            nullable=False,
        ),
    )
    op.add_column(
        "evaluation_datasets",
        sa.Column(
            "review_status",
            sa.String(length=30),
            server_default="not_applicable",
            nullable=False,
        ),
    )
    op.add_column(
        "evaluation_datasets", sa.Column("review_note", sa.Text(), nullable=True)
    )
    op.add_column(
        "evaluation_datasets", sa.Column("reviewed_by", sa.Integer(), nullable=True)
    )
    op.add_column(
        "evaluation_datasets", sa.Column("reviewed_at", sa.DateTime(), nullable=True)
    )
    op.create_foreign_key(
        "fk_evaluation_datasets_reviewed_by_users",
        "evaluation_datasets",
        "users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_evaluation_datasets_data_origin", "evaluation_datasets", ["data_origin"]
    )
    op.create_index(
        "ix_evaluation_datasets_review_status", "evaluation_datasets", ["review_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_datasets_review_status", table_name="evaluation_datasets")
    op.drop_index("ix_evaluation_datasets_data_origin", table_name="evaluation_datasets")
    op.drop_constraint(
        "fk_evaluation_datasets_reviewed_by_users",
        "evaluation_datasets",
        type_="foreignkey",
    )
    op.drop_column("evaluation_datasets", "reviewed_at")
    op.drop_column("evaluation_datasets", "reviewed_by")
    op.drop_column("evaluation_datasets", "review_note")
    op.drop_column("evaluation_datasets", "review_status")
    op.drop_column("evaluation_datasets", "data_origin")
