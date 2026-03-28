"""Unit tests for EditLog store, merge pipeline, and row locking."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.data.pipeline.merge import EditLogMerger
from lingshu.data.writeback.fdb_client import EditLogEntry, EditLogStore, make_entry
from lingshu.data.writeback.lock import RowLock


# ── Helpers ───────────────────────────────────────────────────────

def _entry(
    operation: str = "create",
    field_values: dict[str, Any] | None = None,
    *,
    entry_id: str = "e1",
    tenant_id: str = "t1",
    type_rid: str = "ri.obj.00000000-0000-0000-0000-000000000001",
    primary_key: dict[str, Any] | None = None,
    user_id: str = "u1",
    branch: str = "main",
) -> EditLogEntry:
    return EditLogEntry(
        entry_id=entry_id,
        tenant_id=tenant_id,
        type_rid=type_rid,
        primary_key=primary_key or {"id": 1},
        operation=operation,
        field_values=field_values or {},
        user_id=user_id,
        branch=branch,
    )


# ── EditLogEntry ─────────────────────────────────────────────────

class TestEditLogEntry:
    def test_valid_operations(self) -> None:
        for op in ("create", "update", "delete"):
            entry = _entry(operation=op)
            assert entry.operation == op

    def test_invalid_operation_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid operation"):
            _entry(operation="upsert")

    def test_frozen_dataclass(self) -> None:
        entry = _entry()
        with pytest.raises(AttributeError):
            entry.operation = "delete"  # type: ignore[misc]

    def test_make_entry_generates_id(self) -> None:
        e = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.00000000-0000-0000-0000-000000000001",
            primary_key={"id": 1},
            operation="create",
            field_values={"name": "Alice"},
            user_id="u1",
        )
        assert e.entry_id  # not empty
        assert e.tenant_id == "t1"
        assert e.operation == "create"


# ── EditLogStore ─────────────────────────────────────────────────

class TestEditLogStore:
    @pytest.fixture()
    def store(self) -> EditLogStore:
        return EditLogStore()

    @pytest.mark.asyncio()
    async def test_write_adds_to_session(self, store: EditLogStore) -> None:
        session = AsyncMock()
        session.flush = AsyncMock()
        entry = _entry(operation="create", field_values={"name": "Alice"})

        result = await store.write(entry, session)

        assert result == entry.entry_id
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_write_maps_fields_correctly(self, store: EditLogStore) -> None:
        session = AsyncMock()
        session.flush = AsyncMock()
        entry = _entry(
            operation="update",
            field_values={"status": "active"},
            entry_id="e99",
        )

        await store.write(entry, session)

        row = session.add.call_args[0][0]
        assert row.entry_id == "e99"
        assert row.operation == "update"
        assert row.field_values == {"status": "active"}


# ── EditLogMerger ────────────────────────────────────────────────

class TestEditLogMerger:
    @pytest.fixture()
    def mock_store(self) -> EditLogStore:
        store = MagicMock(spec=EditLogStore)
        return store

    @pytest.fixture()
    def merger(self, mock_store: EditLogStore) -> EditLogMerger:
        return EditLogMerger(mock_store)

    @pytest.mark.asyncio()
    async def test_no_edits_returns_base(self, merger: EditLogMerger, mock_store: MagicMock) -> None:
        mock_store.read_by_key = AsyncMock(return_value=[])
        session = AsyncMock()
        base = {"id": 1, "name": "Alice"}

        result = await merger.merge_row(
            base, "t1", "type1", {"id": 1}, "main", session,
        )

        assert result == base

    @pytest.mark.asyncio()
    async def test_create_operation(self, merger: EditLogMerger, mock_store: MagicMock) -> None:
        mock_store.read_by_key = AsyncMock(return_value=[
            _entry(operation="create", field_values={"id": 1, "name": "Bob"}),
        ])
        session = AsyncMock()

        result = await merger.merge_row(
            None, "t1", "type1", {"id": 1}, "main", session,
        )

        assert result == {"id": 1, "name": "Bob"}

    @pytest.mark.asyncio()
    async def test_update_operation(self, merger: EditLogMerger, mock_store: MagicMock) -> None:
        mock_store.read_by_key = AsyncMock(return_value=[
            _entry(operation="update", field_values={"name": "Charlie"}),
        ])
        session = AsyncMock()
        base = {"id": 1, "name": "Alice", "age": 30}

        result = await merger.merge_row(
            base, "t1", "type1", {"id": 1}, "main", session,
        )

        assert result is not None
        assert result["name"] == "Charlie"
        assert result["age"] == 30  # untouched

    @pytest.mark.asyncio()
    async def test_delete_operation(self, merger: EditLogMerger, mock_store: MagicMock) -> None:
        mock_store.read_by_key = AsyncMock(return_value=[
            _entry(operation="delete"),
        ])
        session = AsyncMock()
        base = {"id": 1, "name": "Alice"}

        result = await merger.merge_row(
            base, "t1", "type1", {"id": 1}, "main", session,
        )

        assert result is None

    @pytest.mark.asyncio()
    async def test_create_then_update_then_delete(
        self, merger: EditLogMerger, mock_store: MagicMock,
    ) -> None:
        mock_store.read_by_key = AsyncMock(return_value=[
            _entry(entry_id="e1", operation="create", field_values={"id": 1, "name": "Alice"}),
            _entry(entry_id="e2", operation="update", field_values={"name": "Bob"}),
            _entry(entry_id="e3", operation="delete"),
        ])
        session = AsyncMock()

        result = await merger.merge_row(
            None, "t1", "type1", {"id": 1}, "main", session,
        )

        assert result is None

    @pytest.mark.asyncio()
    async def test_update_on_none_base_treats_as_create(
        self, merger: EditLogMerger, mock_store: MagicMock,
    ) -> None:
        mock_store.read_by_key = AsyncMock(return_value=[
            _entry(operation="update", field_values={"id": 1, "name": "Alice"}),
        ])
        session = AsyncMock()

        result = await merger.merge_row(
            None, "t1", "type1", {"id": 1}, "main", session,
        )

        assert result == {"id": 1, "name": "Alice"}

    @pytest.mark.asyncio()
    async def test_base_row_not_mutated(self, merger: EditLogMerger, mock_store: MagicMock) -> None:
        mock_store.read_by_key = AsyncMock(return_value=[
            _entry(operation="update", field_values={"name": "Charlie"}),
        ])
        session = AsyncMock()
        base = {"id": 1, "name": "Alice"}

        await merger.merge_row(base, "t1", "type1", {"id": 1}, "main", session)

        assert base["name"] == "Alice"  # original unchanged

    @pytest.mark.asyncio()
    async def test_merge_rows(self, merger: EditLogMerger, mock_store: MagicMock) -> None:
        async def fake_read_by_key(
            tenant_id: str, type_rid: str, primary_key: dict[str, Any],
            branch: str = "main", *, session: Any,
        ) -> list[EditLogEntry]:
            if primary_key == {"id": 1}:
                return [_entry(operation="update", field_values={"name": "Updated"})]
            if primary_key == {"id": 2}:
                return [_entry(operation="delete")]
            return []

        mock_store.read_by_key = AsyncMock(side_effect=fake_read_by_key)
        session = AsyncMock()

        base_rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]

        result = await merger.merge_rows(
            base_rows, "t1", "type1", "id", "main", session,
        )

        assert len(result) == 2  # id=2 deleted
        assert result[0]["name"] == "Updated"
        assert result[1]["name"] == "Charlie"


# ── RowLock ──────────────────────────────────────────────────────

class TestRowLock:
    @pytest.fixture()
    def redis(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture()
    def lock(self, redis: AsyncMock) -> RowLock:
        return RowLock(redis)

    def _pk(self) -> dict[str, Any]:
        return {"id": 42}

    @pytest.mark.asyncio()
    async def test_acquire_success(self, lock: RowLock, redis: AsyncMock) -> None:
        redis.set = AsyncMock(return_value=True)

        result = await lock.acquire("t1", "type1", self._pk(), "user1")

        assert result is True
        redis.set.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_acquire_already_held_by_same_user(
        self, lock: RowLock, redis: AsyncMock,
    ) -> None:
        redis.set = AsyncMock(return_value=False)
        redis.get = AsyncMock(return_value="user1")
        redis.expire = AsyncMock()

        result = await lock.acquire("t1", "type1", self._pk(), "user1")

        assert result is True
        redis.expire.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_acquire_held_by_other_user(
        self, lock: RowLock, redis: AsyncMock,
    ) -> None:
        redis.set = AsyncMock(return_value=False)
        redis.get = AsyncMock(return_value="user2")

        result = await lock.acquire("t1", "type1", self._pk(), "user1")

        assert result is False

    @pytest.mark.asyncio()
    async def test_release_by_owner(self, lock: RowLock, redis: AsyncMock) -> None:
        redis.get = AsyncMock(return_value="user1")
        redis.delete = AsyncMock()

        result = await lock.release("t1", "type1", self._pk(), "user1")

        assert result is True
        redis.delete.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_release_by_non_owner_fails(
        self, lock: RowLock, redis: AsyncMock,
    ) -> None:
        redis.get = AsyncMock(return_value="user2")

        result = await lock.release("t1", "type1", self._pk(), "user1")

        assert result is False

    @pytest.mark.asyncio()
    async def test_is_locked_true(self, lock: RowLock, redis: AsyncMock) -> None:
        redis.get = AsyncMock(return_value="user1")

        locked, holder = await lock.is_locked("t1", "type1", self._pk())

        assert locked is True
        assert holder == "user1"

    @pytest.mark.asyncio()
    async def test_is_locked_false(self, lock: RowLock, redis: AsyncMock) -> None:
        redis.get = AsyncMock(return_value=None)

        locked, holder = await lock.is_locked("t1", "type1", self._pk())

        assert locked is False
        assert holder is None

    def test_make_key_deterministic(self, lock: RowLock) -> None:
        key1 = lock._make_key("t1", "type1", {"id": 1})
        key2 = lock._make_key("t1", "type1", {"id": 1})
        assert key1 == key2
        assert key1.startswith("row_lock:t1:type1:")

    def test_make_key_different_for_different_pks(self, lock: RowLock) -> None:
        key1 = lock._make_key("t1", "type1", {"id": 1})
        key2 = lock._make_key("t1", "type1", {"id": 2})
        assert key1 != key2
