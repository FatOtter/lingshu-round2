"""AsyncPostgresSaver: LangGraph-compatible checkpoint persistence.

Stores and retrieves agent graph checkpoints in PostgreSQL,
enabling conversation state recovery across sessions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AsyncPostgresSaver:
    """Checkpoint saver backed by the ``checkpoints`` / ``checkpoint_writes`` tables.

    Compatible with the LangGraph checkpoint interface so it can be swapped
    with ``langgraph-checkpoint-postgres`` when a full LangGraph integration
    is desired.
    """

    # ── Put / Get Checkpoint ──────────────────────────────────────

    async def put(
        self,
        db: AsyncSession,
        *,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_ns: str = "",
        parent_checkpoint_id: str | None = None,
        checkpoint: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Upsert a checkpoint for the given thread."""
        upsert_sql = text("""
            INSERT INTO checkpoints
                (thread_id, checkpoint_ns, checkpoint_id,
                 parent_checkpoint_id, type, checkpoint, metadata, created_at)
            VALUES
                (:thread_id, :checkpoint_ns, :checkpoint_id,
                 :parent_checkpoint_id, :type, :checkpoint, :metadata, :created_at)
            ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id)
            DO UPDATE SET
                parent_checkpoint_id = EXCLUDED.parent_checkpoint_id,
                checkpoint = EXCLUDED.checkpoint,
                metadata = EXCLUDED.metadata,
                created_at = EXCLUDED.created_at
        """)
        await db.execute(
            upsert_sql,
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "parent_checkpoint_id": parent_checkpoint_id,
                "type": "json",
                "checkpoint": json.dumps(checkpoint),
                "metadata": json.dumps(metadata or {}),
                "created_at": datetime.now(timezone.utc),
            },
        )
        await db.flush()

    async def get(
        self,
        db: AsyncSession,
        *,
        thread_id: str,
        checkpoint_ns: str = "",
        checkpoint_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve the latest (or a specific) checkpoint for a thread.

        Returns ``None`` when no checkpoint exists.
        """
        if checkpoint_id:
            query = text("""
                SELECT checkpoint_id, parent_checkpoint_id, type,
                       checkpoint, metadata, created_at
                FROM checkpoints
                WHERE thread_id = :thread_id
                  AND checkpoint_ns = :checkpoint_ns
                  AND checkpoint_id = :checkpoint_id
            """)
            params: dict[str, Any] = {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        else:
            query = text("""
                SELECT checkpoint_id, parent_checkpoint_id, type,
                       checkpoint, metadata, created_at
                FROM checkpoints
                WHERE thread_id = :thread_id
                  AND checkpoint_ns = :checkpoint_ns
                ORDER BY created_at DESC
                LIMIT 1
            """)
            params = {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }

        result = await db.execute(query, params)
        row = result.first()
        if row is None:
            return None

        checkpoint_data = row.checkpoint
        meta = row.metadata
        # Handle both raw dict (JSONB auto-deserialized) and string
        if isinstance(checkpoint_data, str):
            checkpoint_data = json.loads(checkpoint_data)
        if isinstance(meta, str):
            meta = json.loads(meta)

        return {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": row.checkpoint_id,
            "parent_checkpoint_id": row.parent_checkpoint_id,
            "type": row.type,
            "checkpoint": checkpoint_data,
            "metadata": meta,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def list(
        self,
        db: AsyncSession,
        *,
        thread_id: str,
        checkpoint_ns: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """List checkpoints for a thread, most recent first."""
        query = text("""
            SELECT checkpoint_id, parent_checkpoint_id, type,
                   checkpoint, metadata, created_at
            FROM checkpoints
            WHERE thread_id = :thread_id
              AND checkpoint_ns = :checkpoint_ns
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        result = await db.execute(query, {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "limit": limit,
        })

        items: list[dict[str, Any]] = []
        for row in result.fetchall():
            cp = row.checkpoint
            meta = row.metadata
            if isinstance(cp, str):
                cp = json.loads(cp)
            if isinstance(meta, str):
                meta = json.loads(meta)
            items.append({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": row.checkpoint_id,
                "parent_checkpoint_id": row.parent_checkpoint_id,
                "type": row.type,
                "checkpoint": cp,
                "metadata": meta,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
        return items

    # ── Pending Writes ────────────────────────────────────────────

    async def put_writes(
        self,
        db: AsyncSession,
        *,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_ns: str = "",
        writes: list[tuple[str, str, Any]],
    ) -> None:
        """Buffer pending writes (task_id, channel, value) for a checkpoint."""
        for idx, (task_id, channel, value) in enumerate(writes):
            upsert_sql = text("""
                INSERT INTO checkpoint_writes
                    (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value)
                VALUES
                    (:thread_id, :checkpoint_ns, :checkpoint_id, :task_id, :idx,
                     :channel, :type, :value)
                ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                DO UPDATE SET
                    channel = EXCLUDED.channel,
                    value = EXCLUDED.value
            """)
            await db.execute(upsert_sql, {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "idx": idx,
                "channel": channel,
                "type": "json",
                "value": json.dumps(value) if value is not None else None,
            })
        await db.flush()

    async def get_writes(
        self,
        db: AsyncSession,
        *,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_ns: str = "",
    ) -> list[dict[str, Any]]:
        """Retrieve pending writes for a checkpoint."""
        query = text("""
            SELECT task_id, idx, channel, type, value
            FROM checkpoint_writes
            WHERE thread_id = :thread_id
              AND checkpoint_ns = :checkpoint_ns
              AND checkpoint_id = :checkpoint_id
            ORDER BY idx
        """)
        result = await db.execute(query, {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
        })

        items: list[dict[str, Any]] = []
        for row in result.fetchall():
            val = row.value
            if isinstance(val, str):
                val = json.loads(val)
            items.append({
                "task_id": row.task_id,
                "idx": row.idx,
                "channel": row.channel,
                "type": row.type,
                "value": val,
            })
        return items

    # ── Cleanup ───────────────────────────────────────────────────

    async def delete_thread(
        self,
        db: AsyncSession,
        *,
        thread_id: str,
    ) -> None:
        """Remove all checkpoints and writes for a thread."""
        await db.execute(
            text("DELETE FROM checkpoint_writes WHERE thread_id = :tid"),
            {"tid": thread_id},
        )
        await db.execute(
            text("DELETE FROM checkpoint_blobs WHERE thread_id = :tid"),
            {"tid": thread_id},
        )
        await db.execute(
            text("DELETE FROM checkpoints WHERE thread_id = :tid"),
            {"tid": thread_id},
        )
        await db.flush()
