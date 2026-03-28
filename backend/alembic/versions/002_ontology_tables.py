"""Create snapshots and active_pointers tables for Ontology versioning.

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snapshots",
        sa.Column("snapshot_id", sa.String(), primary_key=True),
        sa.Column("parent_snapshot_id", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("commit_message", sa.Text(), nullable=True),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("entity_changes", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_snapshots_tenant_created", "snapshots", ["tenant_id", "created_at"])

    op.create_table(
        "active_pointers",
        sa.Column("tenant_id", sa.String(), primary_key=True),
        sa.Column("snapshot_id", sa.String(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("active_pointers")
    op.drop_index("ix_snapshots_tenant_created", table_name="snapshots")
    op.drop_table("snapshots")
