"""Empty database baseline.

Revision ID: 000
Revises: None
Create Date: 2026-03-11

This migration serves as the empty database baseline.
Use ``alembic stamp 000`` on an existing database to mark it at the baseline
before applying subsequent migrations.
"""

from collections.abc import Sequence

revision: str = "000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Empty baseline — nothing to create."""


def downgrade() -> None:
    """Empty baseline — nothing to drop."""
