"""Real FoundationDB-backed EditLog store.

Requires: ``pip install foundationdb`` + FDB cluster running.
Falls back to PostgreSQL if the ``fdb`` package is unavailable.

Key schema::

    ("edit", tenant_id, type_rid, pk_hash, iso_timestamp) -> JSON blob

The JSON blob contains all ``EditLogEntry`` fields so the entry can be
fully reconstructed without secondary lookups.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from lingshu.data.writeback.fdb_client import EditLogEntry

logger = logging.getLogger(__name__)

try:
    import fdb  # type: ignore[import-untyped]

    fdb.api_version(730)
    FDB_AVAILABLE = True
except Exception:  # ImportError or RuntimeError if C client missing
    FDB_AVAILABLE = False


class FdbEditLogStore:
    """FoundationDB-backed EditLog store with transactional writes.

    Each edit-log entry is stored as a single KV pair keyed by
    ``(tenant_id, type_rid, pk_hash, timestamp)``.  Reads use
    range-prefix scans so all entries for a given entity are retrieved
    in chronological order.
    """

    def __init__(self, cluster_file: str = "/etc/foundationdb/fdb.cluster") -> None:
        if not FDB_AVAILABLE:
            raise ImportError(
                "foundationdb package is not installed or the FDB C client "
                "library is missing.  Install with: pip install foundationdb"
            )
        self._db = fdb.open(cluster_file)  # type: ignore[attr-defined]
        self._loop = asyncio.get_event_loop()

    # ── Key helpers ────────────────────────────────────────────────

    @staticmethod
    def _pk_hash(primary_key: dict[str, Any]) -> str:
        """Deterministic 16-char hex hash of a primary-key dict."""
        canonical = json.dumps(primary_key, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    @staticmethod
    def _key(
        tenant_id: str,
        type_rid: str,
        pk_hash: str,
        timestamp: str = "",
    ) -> bytes:
        """Build an FDB tuple key.

        ``edit:{tenant}:{type_rid}:{pk_hash}:{timestamp}``
        """
        import fdb as _fdb  # type: ignore[import-untyped]

        parts: tuple[str, ...] = ("edit", tenant_id, type_rid, pk_hash)
        if timestamp:
            parts = (*parts, timestamp)
        return _fdb.tuple.pack(parts)  # type: ignore[attr-defined]

    # ── Write ──────────────────────────────────────────────────────

    async def write(self, entry: EditLogEntry, session: Any = None) -> str:
        """Persist an edit-log entry in FoundationDB. Returns ``entry_id``.

        ``session`` is accepted for interface compatibility but ignored.
        """
        import fdb as _fdb  # type: ignore[import-untyped]

        pk_hash = self._pk_hash(entry.primary_key)
        ts = entry.created_at.isoformat()
        key = self._key(entry.tenant_id, entry.type_rid, pk_hash, ts)
        value = json.dumps(
            {
                "entry_id": entry.entry_id,
                "tenant_id": entry.tenant_id,
                "type_rid": entry.type_rid,
                "operation": entry.operation,
                "primary_key": entry.primary_key,
                "field_values": entry.field_values,
                "user_id": entry.user_id,
                "action_type_rid": entry.action_type_rid,
                "branch": entry.branch,
                "created_at": ts,
            }
        ).encode()

        @_fdb.transactional  # type: ignore[attr-defined]
        def _do_write(tr: Any) -> None:
            tr[key] = value

        await asyncio.get_running_loop().run_in_executor(
            None, _do_write, self._db
        )
        return entry.entry_id

    # ── Read by key ────────────────────────────────────────────────

    async def read_by_key(
        self,
        tenant_id: str,
        type_rid: str,
        primary_key: dict[str, Any],
        branch: str = "main",
        *,
        session: Any = None,
    ) -> list[EditLogEntry]:
        """Read all edit-log entries for a specific entity (chronological)."""
        import fdb as _fdb  # type: ignore[import-untyped]

        pk_hash = self._pk_hash(primary_key)
        prefix = self._key(tenant_id, type_rid, pk_hash)

        @_fdb.transactional  # type: ignore[attr-defined]
        def _do_read(tr: Any) -> list[EditLogEntry]:
            entries: list[EditLogEntry] = []
            for kv in tr.get_range_startswith(prefix):
                data: dict[str, Any] = json.loads(kv.value.decode())
                if data.get("branch", "main") == branch:
                    entries.append(_data_to_entry(data))
            return entries

        return await asyncio.get_running_loop().run_in_executor(
            None, _do_read, self._db
        )

    # ── Read recent ────────────────────────────────────────────────

    async def read_recent(
        self,
        tenant_id: str,
        *,
        branch: str = "main",
        limit: int = 100,
        session: Any = None,
    ) -> list[EditLogEntry]:
        """Read recent edit logs for a tenant (newest first)."""
        import fdb as _fdb  # type: ignore[import-untyped]

        prefix = _fdb.tuple.pack(("edit", tenant_id))  # type: ignore[attr-defined]

        @_fdb.transactional  # type: ignore[attr-defined]
        def _do_read(tr: Any) -> list[EditLogEntry]:
            entries: list[EditLogEntry] = []
            # Over-fetch to account for branch filtering
            for kv in tr.get_range_startswith(prefix, reverse=True, limit=limit * 2):
                data: dict[str, Any] = json.loads(kv.value.decode())
                if data.get("branch", "main") == branch:
                    entries.append(_data_to_entry(data))
                    if len(entries) >= limit:
                        break
            return entries

        return await asyncio.get_running_loop().run_in_executor(
            None, _do_read, self._db
        )


# ── Module-level helper ──────────────────────────────────────────


def _data_to_entry(data: dict[str, Any]) -> EditLogEntry:
    """Reconstruct an ``EditLogEntry`` from a JSON-decoded dict."""
    created_at_raw = data.get("created_at")
    if created_at_raw:
        created_at = datetime.fromisoformat(created_at_raw)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = datetime.now(timezone.utc)

    return EditLogEntry(
        entry_id=data["entry_id"],
        tenant_id=data.get("tenant_id", ""),
        type_rid=data.get("type_rid", ""),
        primary_key=data["primary_key"],
        operation=data["operation"],
        field_values=data["field_values"],
        user_id=data["user_id"],
        action_type_rid=data.get("action_type_rid"),
        branch=data.get("branch", "main"),
        created_at=created_at,
    )
