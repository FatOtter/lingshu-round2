"""Copilot module tables: sessions, models, skills, mcp_connections, sub_agents.

Revision ID: 005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "copilot_sessions",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("context", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("model_rid", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_copilot_sessions_tenant", "copilot_sessions", ["tenant_id"])
    op.create_index(
        "ix_copilot_sessions_tenant_user",
        "copilot_sessions",
        ["tenant_id", "user_id"],
    )

    op.create_table(
        "copilot_models",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("connection", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("parameters", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
    )
    op.create_index("ix_copilot_models_tenant", "copilot_models", ["tenant_id"])

    op.create_table(
        "copilot_skills",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("tool_bindings", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
    )
    op.create_index("ix_copilot_skills_tenant", "copilot_skills", ["tenant_id"])

    op.create_table(
        "mcp_connections",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("transport", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("auth", postgresql.JSONB(), nullable=True),
        sa.Column("discovered_tools", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("status", sa.String(), server_default="disconnected"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
    )
    op.create_index("ix_mcp_connections_tenant", "mcp_connections", ["tenant_id"])

    op.create_table(
        "sub_agents",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model_rid", sa.String(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("tool_bindings", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("safety_policy", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
    )
    op.create_index("ix_sub_agents_tenant", "sub_agents", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("sub_agents")
    op.drop_table("mcp_connections")
    op.drop_table("copilot_skills")
    op.drop_table("copilot_models")
    op.drop_table("copilot_sessions")
