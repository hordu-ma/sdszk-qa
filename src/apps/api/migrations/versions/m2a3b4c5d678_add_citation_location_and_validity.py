"""add citation location and document validity

Revision ID: m2a3b4c5d678
Revises: k1f2a3b4c567
Create Date: 2026-07-17 11:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m2a3b4c5d678"
down_revision: str | None = "k1f2a3b4c567"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents", sa.Column("valid_from", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "knowledge_documents", sa.Column("valid_until", sa.DateTime(), nullable=True)
    )
    op.create_index(
        "ix_knowledge_documents_valid_until", "knowledge_documents", ["valid_until"]
    )
    op.add_column(
        "knowledge_chunks", sa.Column("page_number", sa.Integer(), nullable=True)
    )
    op.add_column(
        "knowledge_chunks", sa.Column("paragraph_start", sa.Integer(), nullable=True)
    )
    op.add_column(
        "knowledge_chunks", sa.Column("paragraph_end", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "paragraph_end")
    op.drop_column("knowledge_chunks", "paragraph_start")
    op.drop_column("knowledge_chunks", "page_number")
    op.drop_index(
        "ix_knowledge_documents_valid_until", table_name="knowledge_documents"
    )
    op.drop_column("knowledge_documents", "valid_until")
    op.drop_column("knowledge_documents", "valid_from")
