"""Create connections and edit_logs tables for Data module.

Revision ID: 003
Revises: 002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("credentials", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="disconnected"),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("rid"),
    )
    op.create_index("ix_connections_tenant", "connections", ["tenant_id"])

    op.create_table(
        "edit_logs",
        sa.Column("entry_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("type_rid", sa.String(), nullable=False),
        sa.Column("primary_key_json", JSONB, nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("field_values", JSONB, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("action_type_rid", sa.String(), nullable=True),
        sa.Column("branch", sa.String(), nullable=False, server_default="main"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index("ix_edit_logs_tenant", "edit_logs", ["tenant_id"])
    op.create_index(
        "ix_editlog_tenant_type_key", "edit_logs", ["tenant_id", "type_rid"]
    )
    op.create_index(
        "ix_editlog_tenant_branch", "edit_logs", ["tenant_id", "branch"]
    )


def downgrade() -> None:
    op.drop_index("ix_editlog_tenant_branch", table_name="edit_logs")
    op.drop_index("ix_editlog_tenant_type_key", table_name="edit_logs")
    op.drop_index("ix_edit_logs_tenant", table_name="edit_logs")
    op.drop_table("edit_logs")
    op.drop_index("ix_connections_tenant", table_name="connections")
    op.drop_table("connections")
