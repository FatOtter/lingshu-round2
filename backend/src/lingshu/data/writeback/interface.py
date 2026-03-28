"""EditLog backend protocol — shared interface for PostgreSQL and FDB stores."""

from __future__ import annotations

from typing import Any, Protocol

from lingshu.data.writeback.fdb_client import EditLogEntry


class EditLogBackend(Protocol):
    """Protocol for EditLog storage backends.

    Both ``EditLogStore`` (PostgreSQL) and ``FdbEditLogStore`` (FoundationDB)
    implement this interface. The ``session`` parameter is required by the
    PostgreSQL backend but ignored by the FDB backend.
    """

    async def write(
        self,
        entry: EditLogEntry,
        session: Any = None,
    ) -> str:
        """Persist an edit-log entry. Returns ``entry_id``."""
        ...

    async def read_by_key(
        self,
        tenant_id: str,
        type_rid: str,
        primary_key: dict[str, Any],
        branch: str = "main",
        *,
        session: Any = None,
    ) -> list[EditLogEntry]:
        """Read all edit-log entries for a specific entity."""
        ...

    async def read_recent(
        self,
        tenant_id: str,
        *,
        branch: str = "main",
        limit: int = 100,
        session: Any = None,
    ) -> list[EditLogEntry]:
        """Read recent edit logs for a tenant."""
        ...
