"""Unit tests for T7: Snapshot field-level diff."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.ontology.repository.snapshot_repo import SnapshotRepository, _compute_field_diff


class TestComputeFieldDiff:
    """Tests for _compute_field_diff helper function."""

    def test_no_changes(self) -> None:
        """Identical dicts should produce empty diff."""
        result = _compute_field_diff(
            {"name": "foo", "age": 42},
            {"name": "foo", "age": 42},
        )
        assert result["added"] == {}
        assert result["removed"] == {}
        assert result["changed"] == {}

    def test_added_field(self) -> None:
        """Field in B but not A should be in 'added'."""
        result = _compute_field_diff(
            {"name": "foo"},
            {"name": "foo", "age": 42},
        )
        assert result["added"] == {"age": 42}
        assert result["removed"] == {}
        assert result["changed"] == {}

    def test_removed_field(self) -> None:
        """Field in A but not B should be in 'removed'."""
        result = _compute_field_diff(
            {"name": "foo", "age": 42},
            {"name": "foo"},
        )
        assert result["removed"] == {"age": 42}
        assert result["added"] == {}

    def test_changed_field(self) -> None:
        """Field with different values should be in 'changed'."""
        result = _compute_field_diff(
            {"name": "foo", "age": 42},
            {"name": "bar", "age": 42},
        )
        assert result["changed"] == {"name": {"old": "foo", "new": "bar"}}

    def test_complex_diff(self) -> None:
        """Multiple changes at once."""
        result = _compute_field_diff(
            {"a": 1, "b": 2, "c": 3},
            {"a": 1, "b": 99, "d": 4},
        )
        assert result["added"] == {"d": 4}
        assert result["removed"] == {"c": 3}
        assert result["changed"] == {"b": {"old": 2, "new": 99}}

    def test_empty_dicts(self) -> None:
        """Empty dicts should produce empty diff."""
        result = _compute_field_diff({}, {})
        assert result == {"added": {}, "removed": {}, "changed": {}}

    def test_both_empty_to_populated(self) -> None:
        """From empty to populated should be all added."""
        result = _compute_field_diff({}, {"x": 1, "y": 2})
        assert result["added"] == {"x": 1, "y": 2}


class TestSnapshotRepositoryFieldDiff:
    """Tests for SnapshotRepository.get_field_diff."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session: AsyncMock) -> SnapshotRepository:
        return SnapshotRepository(mock_session)

    @pytest.mark.asyncio
    async def test_field_diff_between_two_snapshots(self, repo: SnapshotRepository) -> None:
        """Compare entity_data between two snapshots."""
        snap_a = MagicMock()
        snap_a.entity_data = {
            "ri.obj.1": {"display_name": "Old", "description": "desc"},
        }
        snap_b = MagicMock()
        snap_b.entity_data = {
            "ri.obj.1": {"display_name": "New", "description": "desc"},
        }

        repo.get_by_id = AsyncMock(side_effect=[snap_a, snap_b])

        result = await repo.get_field_diff("snap_a", "snap_b")
        assert "ri.obj.1" in result
        assert result["ri.obj.1"]["changed"]["display_name"] == {"old": "Old", "new": "New"}

    @pytest.mark.asyncio
    async def test_field_diff_with_new_entity(self, repo: SnapshotRepository) -> None:
        """Entity in B but not in A should show all fields as added."""
        snap_a = MagicMock()
        snap_a.entity_data = {}
        snap_b = MagicMock()
        snap_b.entity_data = {
            "ri.obj.new": {"display_name": "Created", "api_name": "new_obj"},
        }

        repo.get_by_id = AsyncMock(side_effect=[snap_a, snap_b])

        result = await repo.get_field_diff("snap_a", "snap_b")
        assert "ri.obj.new" in result
        assert result["ri.obj.new"]["added"]["display_name"] == "Created"

    @pytest.mark.asyncio
    async def test_field_diff_with_deleted_entity(self, repo: SnapshotRepository) -> None:
        """Entity in A but not in B should show all fields as removed."""
        snap_a = MagicMock()
        snap_a.entity_data = {
            "ri.obj.old": {"display_name": "Deleted"},
        }
        snap_b = MagicMock()
        snap_b.entity_data = {}

        repo.get_by_id = AsyncMock(side_effect=[snap_a, snap_b])

        result = await repo.get_field_diff("snap_a", "snap_b")
        assert "ri.obj.old" in result
        assert result["ri.obj.old"]["removed"]["display_name"] == "Deleted"

    @pytest.mark.asyncio
    async def test_field_diff_missing_snapshot(self, repo: SnapshotRepository) -> None:
        """Missing snapshot should be treated as empty entity_data."""
        snap_b = MagicMock()
        snap_b.entity_data = {"ri.obj.1": {"name": "test"}}

        repo.get_by_id = AsyncMock(side_effect=[None, snap_b])

        result = await repo.get_field_diff("snap_a", "snap_b")
        assert "ri.obj.1" in result
        assert result["ri.obj.1"]["added"]["name"] == "test"

    @pytest.mark.asyncio
    async def test_field_diff_no_changes(self, repo: SnapshotRepository) -> None:
        """Identical entity_data should produce empty result."""
        snap = MagicMock()
        snap.entity_data = {"ri.obj.1": {"name": "same"}}

        repo.get_by_id = AsyncMock(return_value=snap)

        result = await repo.get_field_diff("snap_a", "snap_b")
        assert result == {}

    @pytest.mark.asyncio
    async def test_field_diff_null_entity_data(self, repo: SnapshotRepository) -> None:
        """Null entity_data should be treated as empty dict."""
        snap_a = MagicMock()
        snap_a.entity_data = None
        snap_b = MagicMock()
        snap_b.entity_data = {"ri.obj.1": {"x": 1}}

        repo.get_by_id = AsyncMock(side_effect=[snap_a, snap_b])

        result = await repo.get_field_diff("snap_a", "snap_b")
        assert "ri.obj.1" in result
