"""EditLog storage — PostgreSQL backend and factory for backend selection.

Two storage backends are available:

* ``EditLogStore`` (this module) — PostgreSQL via SQLAlchemy ``edit_logs`` table.
  This is the default and requires no additional dependencies.
* ``FdbEditLogStore`` (``fdb_store`` module) — real FoundationDB backend.
  Requires the ``foundationdb`` Python package and a running FDB cluster.

Use :func:`create_editlog_store` to obtain the correct backend based on config.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.data.models import EditLog


@dataclass(frozen=True, slots=True)
class EditLogEntry:
    """A single edit log entry."""

    entry_id: str
    tenant_id: str
    type_rid: str
    primary_key: dict[str, Any]
    operation: str  # "create" | "update" | "delete"
    field_values: dict[str, Any]
    user_id: str
    action_type_rid: str | None = None
    branch: str = "main"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.operation not in ("create", "update", "delete"):
            raise ValueError(
                f"Invalid operation: {self.operation!r}. "
                "Must be 'create', 'update', or 'delete'."
            )


def _new_entry_id() -> str:
    return str(uuid.uuid4())


class EditLogStore:
    """PostgreSQL-backed EditLog store.

    Uses SQLAlchemy ``AsyncSession`` to read/write the ``edit_logs`` table.
    This is the default backend; for FoundationDB see ``FdbEditLogStore``
    in :mod:`lingshu.data.writeback.fdb_store`.
    """

    # ── Write ─────────────────────────────────────────────────────

    async def write(self, entry: EditLogEntry, session: AsyncSession) -> str:
        """Write an edit log entry. Returns entry_id."""
        row = EditLog(
            entry_id=entry.entry_id,
            tenant_id=entry.tenant_id,
            type_rid=entry.type_rid,
            primary_key_json=entry.primary_key,
            operation=entry.operation,
            field_values=entry.field_values,
            user_id=entry.user_id,
            action_type_rid=entry.action_type_rid,
            branch=entry.branch,
            created_at=entry.created_at,
        )
        session.add(row)
        await session.flush()
        return entry.entry_id

    # ── Read ──────────────────────────────────────────────────────

    async def read_by_key(
        self,
        tenant_id: str,
        type_rid: str,
        primary_key: dict[str, Any],
        branch: str = "main",
        *,
        session: AsyncSession,
    ) -> list[EditLogEntry]:
        """Read all edit log entries for a specific entity."""
        stmt = (
            select(EditLog)
            .where(
                EditLog.tenant_id == tenant_id,
                EditLog.type_rid == type_rid,
                EditLog.primary_key_json == primary_key,
                EditLog.branch == branch,
            )
            .order_by(EditLog.created_at.asc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_entry(r) for r in rows]

    async def read_recent(
        self,
        tenant_id: str,
        *,
        branch: str = "main",
        limit: int = 100,
        session: AsyncSession,
    ) -> list[EditLogEntry]:
        """Read recent edit logs for a tenant."""
        stmt = (
            select(EditLog)
            .where(
                EditLog.tenant_id == tenant_id,
                EditLog.branch == branch,
            )
            .order_by(EditLog.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_entry(r) for r in rows]

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _to_entry(row: EditLog) -> EditLogEntry:
        return EditLogEntry(
            entry_id=row.entry_id,
            tenant_id=row.tenant_id,
            type_rid=row.type_rid,
            primary_key=row.primary_key_json,
            operation=row.operation,
            field_values=row.field_values,
            user_id=row.user_id,
            action_type_rid=row.action_type_rid,
            branch=row.branch,
            created_at=row.created_at,
        )


def make_entry(
    tenant_id: str,
    type_rid: str,
    primary_key: dict[str, Any],
    operation: str,
    field_values: dict[str, Any],
    user_id: str,
    *,
    action_type_rid: str | None = None,
    branch: str = "main",
) -> EditLogEntry:
    """Convenience factory that auto-generates entry_id and timestamp."""
    return EditLogEntry(
        entry_id=_new_entry_id(),
        tenant_id=tenant_id,
        type_rid=type_rid,
        primary_key=primary_key,
        operation=operation,
        field_values=field_values,
        user_id=user_id,
        action_type_rid=action_type_rid,
        branch=branch,
    )


def create_editlog_store(
    backend: str = "postgres",
    *,
    cluster_file: str = "/etc/foundationdb/fdb.cluster",
) -> EditLogStore:
    """Create an EditLog store based on the configured backend.

    Parameters
    ----------
    backend:
        ``"postgres"`` (default) or ``"fdb"``.
    cluster_file:
        Path to the FDB cluster file. Only used when *backend* is ``"fdb"``.

    Returns
    -------
    An object satisfying the :class:`~lingshu.data.writeback.interface.EditLogBackend`
    protocol.

    Raises
    ------
    ImportError
        If *backend* is ``"fdb"`` but the ``foundationdb`` package is not installed.
    ValueError
        If *backend* is not a recognised value.
    """
    if backend == "postgres":
        return EditLogStore()

    if backend == "fdb":
        from lingshu.data.writeback.fdb_store import FdbEditLogStore

        return FdbEditLogStore(cluster_file=cluster_file)  # type: ignore[return-value]

    raise ValueError(
        f"Unknown editlog backend: {backend!r}. Must be 'postgres' or 'fdb'."
    )
