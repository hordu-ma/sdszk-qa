"""add pilot organizations and user membership

Revision ID: o4c5d6e7f890
Revises: n3b4c5d6e789
Create Date: 2026-07-22 08:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o4c5d6e7f890"
down_revision: str | None = "n3b4c5d6e789"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_CODE = "luyun-pilot-default"
_DEFAULT_NAME = "鲁韵内部试点默认组织"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "status", sa.String(length=30), server_default="pilot_active", nullable=False
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_organizations_code"),
    )
    op.create_index("ix_organizations_code", "organizations", ["code"], unique=True)
    op.create_index("ix_organizations_status", "organizations", ["status"])
    # 默认试点组织：回填存量用户，保证升级后既有账号继续可用
    op.execute(
        sa.text(
            "INSERT INTO organizations (code, name, status, created_at, updated_at) "
            "VALUES (:code, :name, 'pilot_active', now(), now())"
        ).bindparams(code=_DEFAULT_CODE, name=_DEFAULT_NAME)
    )
    op.add_column(
        "users",
        sa.Column("organization_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_foreign_key(
        "fk_users_organization_id_organizations",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # 存量用户回填到默认试点组织（平台 admin 也先归入，可后续显式置空为组织无关运营）
    op.execute(
        sa.text(
            "UPDATE users SET organization_id = "
            "(SELECT id FROM organizations WHERE code = :code)"
        ).bindparams(code=_DEFAULT_CODE)
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_users_organization_id_organizations", "users", type_="foreignkey"
    )
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_column("users", "organization_id")
    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_index("ix_organizations_code", table_name="organizations")
    op.drop_table("organizations")
