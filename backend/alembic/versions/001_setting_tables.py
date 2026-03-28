"""Setting module tables: users, tenants, memberships, refresh_tokens, custom_roles, audit_logs.

Revision ID: 001
Revises: None
Create Date: 2026-03-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = "000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "tenants",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("config", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
    )

    op.create_table(
        "user_tenant_memberships",
        sa.Column("user_rid", sa.String(), nullable=False),
        sa.Column("tenant_rid", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_rid", "tenant_rid"),
        sa.ForeignKeyConstraint(["user_rid"], ["users.rid"]),
        sa.ForeignKeyConstraint(["tenant_rid"], ["tenants.rid"]),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("user_rid", sa.String(), nullable=False),
        sa.Column("tenant_rid", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("token_hash"),
        sa.ForeignKeyConstraint(["user_rid"], ["users.rid"]),
        sa.ForeignKeyConstraint(["tenant_rid"], ["tenants.rid"]),
    )
    op.create_index(
        "ix_refresh_tokens_user_tenant",
        "refresh_tokens",
        ["user_rid", "tenant_rid"],
    )

    op.create_table(
        "custom_roles",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("permissions", postgresql.JSONB(), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_custom_role_tenant_name"),
    )
    op.create_index("ix_custom_roles_tenant_id", "custom_roles", ["tenant_id"])

    op.create_table(
        "audit_logs",
        sa.Column("log_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("module", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_rid", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("log_id"),
    )
    op.create_index(
        "ix_audit_tenant_created", "audit_logs", ["tenant_id", "created_at"]
    )
    op.create_index(
        "ix_audit_tenant_module_created",
        "audit_logs",
        ["tenant_id", "module", "created_at"],
    )
    op.create_index(
        "ix_audit_tenant_user_created",
        "audit_logs",
        ["tenant_id", "user_id", "created_at"],
    )
    op.create_index(
        "ix_audit_tenant_resource",
        "audit_logs",
        ["tenant_id", "resource_type", "resource_rid"],
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("custom_roles")
    op.drop_table("refresh_tokens")
    op.drop_table("user_tenant_memberships")
    op.drop_table("tenants")
    op.drop_table("users")
