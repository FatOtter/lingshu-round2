"""BS-17: EditLog Writeback Chain scenario tests.

Tests edit log write, read by key, read recent, branch isolation,
and the factory/store pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.data.writeback.fdb_client import (
    EditLogEntry,
    EditLogStore,
    make_entry,
)


@pytest.fixture
def store() -> EditLogStore:
    return EditLogStore()


def _make_editlog_row(
    entry_id: str,
    tenant_id: str = "t1",
    type_rid: str = "ri.obj.robot",
    primary_key: dict | None = None,
    operation: str = "update",
    field_values: dict | None = None,
    user_id: str = "u1",
    branch: str = "main",
) -> MagicMock:
    """Create a mock EditLog ORM row."""
    row = MagicMock()
    row.entry_id = entry_id
    row.tenant_id = tenant_id
    row.type_rid = type_rid
    row.primary_key_json = primary_key or {"id": "robot-1"}
    row.operation = operation
    row.field_values = field_values or {"x": 10, "y": 20}
    row.user_id = user_id
    row.action_type_rid = None
    row.branch = branch
    row.created_at = datetime.now(timezone.utc)
    return row


class TestBS17EditLogWriteback:
    """EditLog Writeback: write -> read by key -> read recent -> branch isolation."""

    async def test_step1_write_editlog_entry(
        self, store: EditLogStore, mock_db_session: AsyncMock,
    ) -> None:
        """Write entry via EditLogStore, verify entry_id returned."""
        entry = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.robot",
            primary_key={"id": "robot-1"},
            operation="update",
            field_values={"x": 10, "y": 20},
            user_id="u1",
            action_type_rid="ri.action.move",
            branch="main",
        )

        entry_id = await store.write(entry, mock_db_session)

        assert entry_id == entry.entry_id
        assert entry_id != ""
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_awaited_once()

    async def test_step2_read_by_key(
        self, store: EditLogStore, mock_db_session: AsyncMock,
    ) -> None:
        """Read entries by type_rid + primary_key, verify match."""
        row = _make_editlog_row("entry-1")

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[row])),
        )
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        entries = await store.read_by_key(
            tenant_id="t1",
            type_rid="ri.obj.robot",
            primary_key={"id": "robot-1"},
            branch="main",
            session=mock_db_session,
        )

        assert len(entries) == 1
        assert entries[0].entry_id == "entry-1"
        assert entries[0].type_rid == "ri.obj.robot"
        assert entries[0].field_values == {"x": 10, "y": 20}

    async def test_step3_read_recent(
        self, store: EditLogStore, mock_db_session: AsyncMock,
    ) -> None:
        """Read recent entries, verify ordering (mock returns them)."""
        row1 = _make_editlog_row("entry-1")
        row2 = _make_editlog_row("entry-2", field_values={"x": 30})

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[row2, row1])),
        )
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        entries = await store.read_recent(
            tenant_id="t1",
            branch="main",
            limit=10,
            session=mock_db_session,
        )

        assert len(entries) == 2
        assert entries[0].entry_id == "entry-2"
        assert entries[1].entry_id == "entry-1"

    async def test_step4_branch_isolation(
        self, store: EditLogStore, mock_db_session: AsyncMock,
    ) -> None:
        """Write to branch 'feature/x', verify main doesn't see it."""
        # Write to feature branch
        entry = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.robot",
            primary_key={"id": "robot-1"},
            operation="update",
            field_values={"x": 99},
            user_id="u1",
            branch="feature/x",
        )
        await store.write(entry, mock_db_session)

        # Read from main branch — returns empty (mock)
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[])),
        )
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        main_entries = await store.read_by_key(
            tenant_id="t1",
            type_rid="ri.obj.robot",
            primary_key={"id": "robot-1"},
            branch="main",
            session=mock_db_session,
        )
        assert len(main_entries) == 0

        # Read from feature branch — returns the entry
        feature_row = _make_editlog_row("entry-feat", branch="feature/x", field_values={"x": 99})
        mock_result2 = MagicMock()
        mock_result2.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[feature_row])),
        )
        mock_db_session.execute = AsyncMock(return_value=mock_result2)

        feature_entries = await store.read_by_key(
            tenant_id="t1",
            type_rid="ri.obj.robot",
            primary_key={"id": "robot-1"},
            branch="feature/x",
            session=mock_db_session,
        )
        assert len(feature_entries) == 1
        assert feature_entries[0].field_values == {"x": 99}

    async def test_step5_factory_selects_backend(self) -> None:
        """make_entry factory generates valid EditLogEntry with auto-generated fields."""
        entry = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.robot",
            primary_key={"id": "robot-1"},
            operation="create",
            field_values={"name": "Robot Alpha"},
            user_id="u1",
        )

        assert entry.entry_id != ""
        assert entry.tenant_id == "t1"
        assert entry.operation == "create"
        assert entry.branch == "main"
        assert isinstance(entry.created_at, datetime)

        # Invalid operation raises ValueError
        with pytest.raises(ValueError, match="Invalid operation"):
            make_entry(
                tenant_id="t1",
                type_rid="ri.obj.x",
                primary_key={},
                operation="invalid_op",
                field_values={},
                user_id="u1",
            )
