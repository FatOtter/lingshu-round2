"""LangGraph checkpoint tables for AsyncPostgresSaver.

Revision ID: 006
Revises: 005
Create Date: 2026-03-11

Creates the tables used by LangGraph's AsyncPostgresSaver to persist
agent conversation state (checkpoints) and pending writes.
Schema follows the langgraph-checkpoint-postgres specification.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006"
down_revision: str | None = "005b"
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Main checkpoint table: stores serialised graph state per thread.
    op.create_table(
        "checkpoints",
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("checkpoint_ns", sa.String(), server_default="", nullable=False),
        sa.Column("checkpoint_id", sa.String(), nullable=False),
        sa.Column("parent_checkpoint_id", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("checkpoint", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id"),
    )

    # Pending writes: buffered writes not yet folded into a checkpoint.
    op.create_table(
        "checkpoint_writes",
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("checkpoint_ns", sa.String(), server_default="", nullable=False),
        sa.Column("checkpoint_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint(
            "thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx",
        ),
    )

    # Checkpoint blobs: large binary payloads referenced by checkpoints.
    op.create_table(
        "checkpoint_blobs",
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("checkpoint_ns", sa.String(), server_default="", nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("blob", sa.LargeBinary(), nullable=True),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "channel", "version"),
    )


def downgrade() -> None:
    op.drop_table("checkpoint_blobs")
    op.drop_table("checkpoint_writes")
    op.drop_table("checkpoints")
