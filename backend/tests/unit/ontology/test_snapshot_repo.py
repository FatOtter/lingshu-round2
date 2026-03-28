"""Unit tests for SnapshotRepository and _compute_field_diff."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.ontology.models import ActivePointer, Snapshot
from lingshu.ontology.repository.snapshot_repo import (
    SnapshotRepository,
    _compute_field_diff,
)


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _mock_scalar(session: AsyncMock, value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute = AsyncMock(return_value=result)


class TestSnapshotCreate:
    @pytest.mark.asyncio
    async def test_create(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        snap = Snapshot(snapshot_id="s1", tenant_id="t1", author="u1", entity_changes={})
        result = await repo.create(snap)
        session.add.assert_called_once_with(snap)
        assert result is snap


class TestSnapshotGetById:
    @pytest.mark.asyncio
    async def test_found(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        snap = Snapshot(snapshot_id="s1", tenant_id="t1", author="u1", entity_changes={})
        _mock_scalar(session, snap)
        result = await repo.get_by_id("s1")
        assert result is snap

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        _mock_scalar(session, None)
        assert await repo.get_by_id("s1") is None


class TestSnapshotListByTenant:
    @pytest.mark.asyncio
    async def test_list(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        snaps = [Snapshot(snapshot_id=f"s{i}", tenant_id="t1", author="u1", entity_changes={}) for i in range(2)]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = snaps
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_by_tenant("t1")
        assert total == 2
        assert len(result) == 2


class TestActivePointer:
    @pytest.mark.asyncio
    async def test_get_active_pointer_found(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        pointer = ActivePointer(tenant_id="t1", snapshot_id="s1")
        _mock_scalar(session, pointer)
        result = await repo.get_active_pointer("t1")
        assert result is pointer

    @pytest.mark.asyncio
    async def test_get_active_pointer_not_found(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        _mock_scalar(session, None)
        assert await repo.get_active_pointer("t1") is None

    @pytest.mark.asyncio
    async def test_set_active_pointer_creates_new(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        # get_active_pointer returns None (no existing)
        _mock_scalar(session, None)
        result = await repo.set_active_pointer("t1", "s1")
        assert result.tenant_id == "t1"
        assert result.snapshot_id == "s1"
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_active_pointer_updates_existing(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        existing = ActivePointer(tenant_id="t1", snapshot_id="s_old")
        # First execute returns existing pointer, second is the update
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = existing
        update_result = AsyncMock()
        session.execute = AsyncMock(side_effect=[get_result, update_result])
        result = await repo.set_active_pointer("t1", "s_new")
        assert result.snapshot_id == "s_new"


class TestGetDiff:
    @pytest.mark.asyncio
    async def test_snapshot_not_found(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        _mock_scalar(session, None)
        result = await repo.get_diff("s1", "s2")
        assert result == {"changes": {}}

    @pytest.mark.asyncio
    async def test_with_current(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        snap = MagicMock()
        snap.entity_changes = {"obj1": "created"}
        current = MagicMock()
        current.entity_changes = {"obj2": "updated"}
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=snap)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=current)),
        ])
        result = await repo.get_diff("s1", "s2")
        assert result["snapshot_changes"] == {"obj1": "created"}
        assert result["current_changes"] == {"obj2": "updated"}

    @pytest.mark.asyncio
    async def test_without_current(self):
        session = _make_session()
        repo = SnapshotRepository(session)
        snap = MagicMock()
        snap.entity_changes = {"obj1": "created"}
        _mock_scalar(session, snap)
        result = await repo.get_diff("s1", None)
        assert result["snapshot_changes"] == {"obj1": "created"}
        assert result["current_changes"] == {}


class TestGetFieldDiff:
    @pytest.mark.asyncio
    async def test_both_exist(self):
        session = _make_session()
        repo = SnapshotRepository(session)

        snap_a = MagicMock()
        snap_a.entity_data = {"r1": {"name": "old", "desc": "x"}}
        snap_b = MagicMock()
        snap_b.entity_data = {"r1": {"name": "new", "status": "active"}}

        session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=snap_a)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=snap_b)),
        ])

        result = await repo.get_field_diff("s1", "s2")
        assert "r1" in result
        assert result["r1"]["changed"]["name"] == {"old": "old", "new": "new"}
        assert "status" in result["r1"]["added"]
        assert "desc" in result["r1"]["removed"]

    @pytest.mark.asyncio
    async def test_no_diff(self):
        session = _make_session()
        repo = SnapshotRepository(session)

        snap_a = MagicMock()
        snap_a.entity_data = {"r1": {"name": "same"}}
        snap_b = MagicMock()
        snap_b.entity_data = {"r1": {"name": "same"}}

        session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=snap_a)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=snap_b)),
        ])

        result = await repo.get_field_diff("s1", "s2")
        assert result == {}


class TestComputeFieldDiff:
    def test_added_fields(self):
        result = _compute_field_diff({}, {"a": 1, "b": 2})
        assert result["added"] == {"a": 1, "b": 2}
        assert result["removed"] == {}
        assert result["changed"] == {}

    def test_removed_fields(self):
        result = _compute_field_diff({"a": 1, "b": 2}, {})
        assert result["removed"] == {"a": 1, "b": 2}
        assert result["added"] == {}

    def test_changed_fields(self):
        result = _compute_field_diff({"a": 1}, {"a": 2})
        assert result["changed"] == {"a": {"old": 1, "new": 2}}

    def test_no_changes(self):
        result = _compute_field_diff({"a": 1}, {"a": 1})
        assert result["added"] == {}
        assert result["removed"] == {}
        assert result["changed"] == {}

    def test_mixed(self):
        result = _compute_field_diff(
            {"keep": "same", "change": "old", "remove": "x"},
            {"keep": "same", "change": "new", "add": "y"},
        )
        assert result["added"] == {"add": "y"}
        assert result["removed"] == {"remove": "x"}
        assert result["changed"] == {"change": {"old": "old", "new": "new"}}
