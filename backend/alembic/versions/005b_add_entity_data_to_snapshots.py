"""Add entity_data JSONB column to snapshots table for field-level diff.

Revision ID: 005b
Revises: 005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005b"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "snapshots",
        sa.Column("entity_data", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("snapshots", "entity_data")
