"""Unit tests for FDB EditLog backend, factory function, and interface."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.data.writeback.fdb_client import (
    EditLogEntry,
    EditLogStore,
    create_editlog_store,
    make_entry,
)
from lingshu.data.writeback.fdb_store import FDB_AVAILABLE, _data_to_entry


# ── EditLogEntry creation and validation ──────────────────────────


class TestEditLogEntryValidation:
    """Verify EditLogEntry dataclass invariants."""

    def test_valid_create_operation(self) -> None:
        entry = EditLogEntry(
            entry_id="e1",
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={"name": "Alice"},
            user_id="u1",
        )
        assert entry.operation == "create"
        assert entry.branch == "main"

    def test_valid_update_operation(self) -> None:
        entry = EditLogEntry(
            entry_id="e2",
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="update",
            field_values={"name": "Bob"},
            user_id="u1",
        )
        assert entry.operation == "update"

    def test_valid_delete_operation(self) -> None:
        entry = EditLogEntry(
            entry_id="e3",
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="delete",
            field_values={},
            user_id="u1",
        )
        assert entry.operation == "delete"

    def test_invalid_operation_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid operation"):
            EditLogEntry(
                entry_id="e4",
                tenant_id="t1",
                type_rid="ri.obj.001",
                primary_key={"id": 1},
                operation="upsert",
                field_values={},
                user_id="u1",
            )

    def test_frozen_prevents_mutation(self) -> None:
        entry = EditLogEntry(
            entry_id="e5",
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={},
            user_id="u1",
        )
        with pytest.raises(AttributeError):
            entry.operation = "delete"  # type: ignore[misc]

    def test_default_branch_is_main(self) -> None:
        entry = EditLogEntry(
            entry_id="e6",
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={},
            user_id="u1",
        )
        assert entry.branch == "main"

    def test_custom_branch(self) -> None:
        entry = EditLogEntry(
            entry_id="e7",
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={},
            user_id="u1",
            branch="feature-x",
        )
        assert entry.branch == "feature-x"

    def test_created_at_has_utc_timezone(self) -> None:
        entry = EditLogEntry(
            entry_id="e8",
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={},
            user_id="u1",
        )
        assert entry.created_at.tzinfo is not None


# ── make_entry factory ────────────────────────────────────────────


class TestMakeEntry:
    """Verify the make_entry convenience factory."""

    def test_generates_entry_id(self) -> None:
        e = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={"name": "Alice"},
            user_id="u1",
        )
        assert e.entry_id  # non-empty
        assert len(e.entry_id) == 36  # UUID format

    def test_auto_generates_timestamp(self) -> None:
        e = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="update",
            field_values={},
            user_id="u1",
        )
        assert isinstance(e.created_at, datetime)
        assert e.created_at.tzinfo is not None

    def test_passes_through_optional_fields(self) -> None:
        e = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={"name": "Test"},
            user_id="u1",
            action_type_rid="ri.action.abc",
            branch="dev",
        )
        assert e.action_type_rid == "ri.action.abc"
        assert e.branch == "dev"

    def test_two_calls_generate_different_ids(self) -> None:
        e1 = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={},
            user_id="u1",
        )
        e2 = make_entry(
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={},
            user_id="u1",
        )
        assert e1.entry_id != e2.entry_id


# ── create_editlog_store factory ──────────────────────────────────


class TestCreateEditlogStore:
    """Verify backend selection factory."""

    def test_postgres_backend_returns_editlog_store(self) -> None:
        store = create_editlog_store("postgres")
        assert isinstance(store, EditLogStore)

    def test_default_backend_is_postgres(self) -> None:
        store = create_editlog_store()
        assert isinstance(store, EditLogStore)

    def test_fdb_backend_raises_when_unavailable(self) -> None:
        """When the fdb package is not installed, creating an FDB store raises."""
        if FDB_AVAILABLE:
            pytest.skip("fdb package is installed — cannot test ImportError path")
        with pytest.raises(ImportError, match="foundationdb"):
            create_editlog_store("fdb")

    def test_unknown_backend_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown editlog backend"):
            create_editlog_store("mysql")


# ── _data_to_entry helper ────────────────────────────────────────


class TestDataToEntry:
    """Verify JSON-dict to EditLogEntry reconstruction."""

    def test_full_data(self) -> None:
        data: dict[str, Any] = {
            "entry_id": "e1",
            "tenant_id": "t1",
            "type_rid": "ri.obj.001",
            "primary_key": {"id": 42},
            "operation": "update",
            "field_values": {"name": "Bob"},
            "user_id": "u1",
            "action_type_rid": "ri.action.xyz",
            "branch": "dev",
            "created_at": "2026-03-13T10:00:00+00:00",
        }
        entry = _data_to_entry(data)
        assert entry.entry_id == "e1"
        assert entry.tenant_id == "t1"
        assert entry.type_rid == "ri.obj.001"
        assert entry.primary_key == {"id": 42}
        assert entry.operation == "update"
        assert entry.field_values == {"name": "Bob"}
        assert entry.user_id == "u1"
        assert entry.action_type_rid == "ri.action.xyz"
        assert entry.branch == "dev"
        assert entry.created_at.tzinfo is not None

    def test_missing_optional_fields(self) -> None:
        data: dict[str, Any] = {
            "entry_id": "e2",
            "primary_key": {"id": 1},
            "operation": "create",
            "field_values": {},
            "user_id": "u1",
        }
        entry = _data_to_entry(data)
        assert entry.tenant_id == ""
        assert entry.type_rid == ""
        assert entry.action_type_rid is None
        assert entry.branch == "main"

    def test_naive_timestamp_gets_utc(self) -> None:
        data: dict[str, Any] = {
            "entry_id": "e3",
            "primary_key": {"id": 1},
            "operation": "delete",
            "field_values": {},
            "user_id": "u1",
            "created_at": "2026-03-13T10:00:00",
        }
        entry = _data_to_entry(data)
        assert entry.created_at.tzinfo == timezone.utc

    def test_missing_timestamp_uses_now(self) -> None:
        data: dict[str, Any] = {
            "entry_id": "e4",
            "primary_key": {"id": 1},
            "operation": "create",
            "field_values": {},
            "user_id": "u1",
        }
        before = datetime.now(timezone.utc)
        entry = _data_to_entry(data)
        after = datetime.now(timezone.utc)
        assert before <= entry.created_at <= after


# ── PostgreSQL EditLogStore write/read (mocked session) ───────────


class TestEditLogStoreWrite:
    """Verify PostgreSQL EditLogStore write behaviour with mocked session."""

    @pytest.fixture()
    def store(self) -> EditLogStore:
        return EditLogStore()

    @pytest.mark.asyncio()
    async def test_write_returns_entry_id(self, store: EditLogStore) -> None:
        session = AsyncMock()
        session.flush = AsyncMock()
        entry = EditLogEntry(
            entry_id="e-write-1",
            tenant_id="t1",
            type_rid="ri.obj.001",
            primary_key={"id": 1},
            operation="create",
            field_values={"name": "Alice"},
            user_id="u1",
        )
        result = await store.write(entry, session)
        assert result == "e-write-1"
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_write_maps_all_fields(self, store: EditLogStore) -> None:
        session = AsyncMock()
        session.flush = AsyncMock()
        entry = EditLogEntry(
            entry_id="e-write-2",
            tenant_id="t1",
            type_rid="ri.obj.002",
            primary_key={"id": 99},
            operation="update",
            field_values={"status": "active"},
            user_id="u2",
            action_type_rid="ri.action.abc",
            branch="dev",
        )
        await store.write(entry, session)
        row = session.add.call_args[0][0]
        assert row.entry_id == "e-write-2"
        assert row.tenant_id == "t1"
        assert row.type_rid == "ri.obj.002"
        assert row.operation == "update"
        assert row.field_values == {"status": "active"}
        assert row.user_id == "u2"
        assert row.action_type_rid == "ri.action.abc"
        assert row.branch == "dev"


# ── FdbEditLogStore helper methods ────────────────────────────────


class TestFdbEditLogStoreHelpers:
    """Test static/class methods of FdbEditLogStore without requiring fdb."""

    def test_pk_hash_deterministic(self) -> None:
        from lingshu.data.writeback.fdb_store import FdbEditLogStore

        h1 = FdbEditLogStore._pk_hash({"id": 1})
        h2 = FdbEditLogStore._pk_hash({"id": 1})
        assert h1 == h2
        assert len(h1) == 16

    def test_pk_hash_differs_for_different_keys(self) -> None:
        from lingshu.data.writeback.fdb_store import FdbEditLogStore

        h1 = FdbEditLogStore._pk_hash({"id": 1})
        h2 = FdbEditLogStore._pk_hash({"id": 2})
        assert h1 != h2

    def test_pk_hash_order_independent(self) -> None:
        from lingshu.data.writeback.fdb_store import FdbEditLogStore

        h1 = FdbEditLogStore._pk_hash({"a": 1, "b": 2})
        h2 = FdbEditLogStore._pk_hash({"b": 2, "a": 1})
        assert h1 == h2
