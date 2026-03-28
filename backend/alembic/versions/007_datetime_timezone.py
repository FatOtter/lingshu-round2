"""Add timezone to all DateTime columns.

Revision ID: 007
Revises: 006
Create Date: 2026-03-12
"""

from alembic import op

revision: str = "007"
down_revision: str = "006"
branch_labels = None
depends_on = None

# (table_name, column_name) for all TIMESTAMP WITHOUT TIME ZONE columns
_COLUMNS = [
    # setting (001)
    ("users", "created_at"),
    ("users", "updated_at"),
    ("tenants", "created_at"),
    ("tenants", "updated_at"),
    ("user_tenant_memberships", "created_at"),
    ("refresh_tokens", "expires_at"),
    ("refresh_tokens", "revoked_at"),
    ("refresh_tokens", "created_at"),
    ("custom_roles", "created_at"),
    ("custom_roles", "updated_at"),
    ("audit_logs", "created_at"),
    # ontology (002)
    ("snapshots", "created_at"),
    ("active_pointers", "updated_at"),
    # data (003)
    ("connections", "last_tested_at"),
    ("connections", "created_at"),
    ("connections", "updated_at"),
    # function (004)
    ("global_functions", "created_at"),
    ("global_functions", "updated_at"),
    ("workflows", "created_at"),
    ("workflows", "updated_at"),
    ("executions", "started_at"),
    ("executions", "completed_at"),
    ("executions", "confirmed_at"),
    # copilot (005)
    ("copilot_sessions", "created_at"),
    ("copilot_sessions", "last_active_at"),
    ("copilot_models", "created_at"),
    ("copilot_models", "updated_at"),
    ("copilot_skills", "created_at"),
    ("copilot_skills", "updated_at"),
    ("mcp_connections", "created_at"),
    ("mcp_connections", "updated_at"),
    ("sub_agents", "created_at"),
    ("sub_agents", "updated_at"),
    # langgraph checkpoint (006)
    ("checkpoints", "created_at"),
]


def upgrade() -> None:
    for table, col in _COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{col}" '
            f"TYPE TIMESTAMP WITH TIME ZONE USING \"{col}\" AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    for table, col in _COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{col}" '
            f"TYPE TIMESTAMP WITHOUT TIME ZONE"
        )
