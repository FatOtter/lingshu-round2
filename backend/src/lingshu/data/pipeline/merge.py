"""Merge edit logs with base data at read time."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.data.writeback.interface import EditLogBackend


class EditLogMerger:
    """Apply edit-log entries on top of base rows to produce the current view.

    For each entity the merge replays all edit-log entries (oldest first):

    * **create** -- use ``field_values`` as the initial row.
    * **update** -- overlay ``field_values`` onto the existing row.
    * **delete** -- mark the row as deleted (``None``).
    """

    def __init__(self, edit_log_store: EditLogBackend) -> None:
        self._store = edit_log_store

    async def merge_row(
        self,
        base_row: dict[str, Any] | None,
        tenant_id: str,
        type_rid: str,
        primary_key: dict[str, Any],
        branch: str,
        session: AsyncSession,
    ) -> dict[str, Any] | None:
        """Apply edit logs to a base row to get the current view."""
        entries = await self._store.read_by_key(
            tenant_id, type_rid, primary_key, branch, session=session,
        )

        if not entries:
            return base_row

        row = copy.deepcopy(base_row) if base_row is not None else None

        for entry in entries:
            if entry.operation == "create":
                row = dict(entry.field_values)
            elif entry.operation == "update":
                if row is None:
                    # Update on a non-existent row -- treat as create
                    row = dict(entry.field_values)
                else:
                    row = {**row, **entry.field_values}
            elif entry.operation == "delete":
                row = None

        return row

    async def merge_rows(
        self,
        base_rows: list[dict[str, Any]],
        tenant_id: str,
        type_rid: str,
        primary_key_field: str,
        branch: str,
        session: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Merge edit logs into a list of base rows.

        Each row must contain ``primary_key_field`` so we can look up
        its corresponding edit-log entries.
        """
        merged: list[dict[str, Any]] = []

        for base_row in base_rows:
            pk_value = base_row.get(primary_key_field)
            if pk_value is None:
                merged.append(base_row)
                continue

            primary_key = {primary_key_field: pk_value}
            result = await self.merge_row(
                base_row, tenant_id, type_rid, primary_key, branch, session,
            )
            if result is not None:
                merged.append(result)

        return merged
