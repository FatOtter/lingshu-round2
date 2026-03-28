"""Function module tables: global_functions, workflows, executions.

Revision ID: 004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "global_functions",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("implementation", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
    )
    op.create_index("ix_global_functions_tenant", "global_functions", ["tenant_id"])
    op.create_index(
        "ix_global_functions_tenant_api_name",
        "global_functions",
        ["tenant_id", "api_name"],
        unique=True,
    )

    op.create_table(
        "workflows",
        sa.Column("rid", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("api_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("definition", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("safety_level", sa.String(), server_default="SAFETY_READ_ONLY"),
        sa.Column("side_effects", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rid"),
    )
    op.create_index("ix_workflows_tenant", "workflows", ["tenant_id"])
    op.create_index(
        "ix_workflows_tenant_api_name",
        "workflows",
        ["tenant_id", "api_name"],
        unique=True,
    )

    op.create_table(
        "executions",
        sa.Column("execution_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("capability_type", sa.String(), nullable=False),
        sa.Column("capability_rid", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("params", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("safety_level", sa.String(), nullable=True),
        sa.Column("side_effects", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("branch", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("execution_id"),
    )
    op.create_index("ix_executions_tenant", "executions", ["tenant_id"])
    op.create_index(
        "ix_executions_tenant_status",
        "executions",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_executions_tenant_started",
        "executions",
        ["tenant_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_table("executions")
    op.drop_table("workflows")
    op.drop_table("global_functions")
