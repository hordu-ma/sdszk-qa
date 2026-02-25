"""Sizheng schema cleanup

Remove medical-specific tables (scores, test_requests) and columns,
rename case fields to match sizheng (political education) domain.

Revision ID: d5f2a7b8e301
Revises: c4a1e8d93f22
Create Date: 2026-02-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f2a7b8e301"
down_revision: str | Sequence[str] | None = "c4a1e8d93f22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: remove medical artifacts, rename fields for sizheng."""
    # --- 1. Drop scores and test_requests tables ---
    op.drop_index(op.f("ix_scores_session_id"), table_name="scores")
    op.drop_table("scores")
    op.drop_index(op.f("ix_test_requests_session_id"), table_name="test_requests")
    op.drop_table("test_requests")

    # --- 2. Drop sessions.submitted_diagnosis ---
    op.drop_column("sessions", "submitted_diagnosis")

    # --- 3. Rename cases columns ---
    op.alter_column("cases", "patient_info", new_column_name="context_info")
    op.alter_column("cases", "chief_complaint", new_column_name="core_question")
    op.alter_column("cases", "present_illness", new_column_name="scenario_text")
    op.alter_column("cases", "past_history", new_column_name="supplementary_info")
    op.alter_column("cases", "standard_diagnosis", new_column_name="reference_answer")

    # --- 4. Drop medical-only columns from cases ---
    op.drop_column("cases", "physical_exam")
    op.drop_column("cases", "available_tests")
    op.drop_column("cases", "recommended_tests")
    op.drop_column("cases", "marriage_childbearing_history")
    op.drop_column("cases", "family_history")
    op.drop_column("cases", "case_number")


def downgrade() -> None:
    """Downgrade schema: restore medical tables and columns."""
    # --- 4. Restore dropped cases columns ---
    op.add_column(
        "cases",
        sa.Column("case_number", sa.Integer(), nullable=True, comment="随机病例序号（1-106）"),
    )
    op.add_column(
        "cases",
        sa.Column("family_history", sa.Text(), nullable=True, comment="家族史"),
    )
    op.add_column(
        "cases",
        sa.Column("marriage_childbearing_history", sa.Text(), nullable=True, comment="婚育个人史"),
    )
    op.add_column(
        "cases",
        sa.Column("recommended_tests", sa.JSON(), nullable=True, comment="推荐检查项列表"),
    )
    op.add_column(
        "cases",
        sa.Column(
            "available_tests",
            sa.JSON(),
            nullable=False,
            server_default="[]",
            comment="可申请的检查项及结果",
        ),
    )
    op.add_column(
        "cases",
        sa.Column(
            "physical_exam",
            sa.JSON(),
            nullable=False,
            server_default="{}",
            comment="体格检查（可见体征和按需提供的体征）",
        ),
    )

    # --- 3. Restore original column names ---
    op.alter_column("cases", "reference_answer", new_column_name="standard_diagnosis")
    op.alter_column("cases", "supplementary_info", new_column_name="past_history")
    op.alter_column("cases", "scenario_text", new_column_name="present_illness")
    op.alter_column("cases", "core_question", new_column_name="chief_complaint")
    op.alter_column("cases", "context_info", new_column_name="patient_info")

    # --- 2. Restore sessions.submitted_diagnosis ---
    op.add_column(
        "sessions",
        sa.Column(
            "submitted_diagnosis",
            sa.Text(),
            nullable=True,
            comment="学生提交的诊断结论",
        ),
    )

    # --- 1. Recreate scores and test_requests tables ---
    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), nullable=False, comment="评分ID"),
        sa.Column("session_id", sa.Integer(), nullable=False, comment="会话ID（唯一）"),
        sa.Column(
            "total_score",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            comment="总分（0-100）",
        ),
        sa.Column("dimensions", sa.JSON(), nullable=False, comment="各维度得分"),
        sa.Column("scoring_details", sa.JSON(), nullable=False, comment="评分详情"),
        sa.Column("scoring_method", sa.String(), nullable=False, comment="评分方式"),
        sa.Column("model_version", sa.String(), nullable=True, comment="模型版本"),
        sa.Column(
            "scored_at",
            sa.DateTime(),
            server_default="now()",
            nullable=False,
            comment="评分时间",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_scores_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scores")),
    )
    op.create_index(op.f("ix_scores_session_id"), "scores", ["session_id"], unique=True)

    op.create_table(
        "test_requests",
        sa.Column("id", sa.Integer(), nullable=False, comment="检查申请ID"),
        sa.Column("session_id", sa.Integer(), nullable=False, comment="会话ID"),
        sa.Column("test_type", sa.String(length=50), nullable=False, comment="检查类型"),
        sa.Column("test_name", sa.String(length=100), nullable=False, comment="检查名称"),
        sa.Column("result", sa.JSON(), nullable=False, comment="检查结果"),
        sa.Column(
            "requested_at",
            sa.DateTime(),
            server_default="now()",
            nullable=False,
            comment="申请时间",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_test_requests_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_requests")),
    )
    op.create_index(
        op.f("ix_test_requests_session_id"), "test_requests", ["session_id"], unique=False
    )
