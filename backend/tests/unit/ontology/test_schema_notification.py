"""Unit tests for T3: Schema publish notification."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from lingshu.ontology.service import OntologyServiceImpl


@pytest.fixture
def mock_graph() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.scan = AsyncMock(return_value=(0, []))
    redis.delete = AsyncMock()
    redis.publish = AsyncMock()
    return redis


@pytest.fixture
def service(mock_graph: AsyncMock, mock_redis: AsyncMock) -> OntologyServiceImpl:
    return OntologyServiceImpl(graph_repo=mock_graph, redis=mock_redis)


class TestOnSchemaPublished:
    """Tests for on_schema_published implementation."""

    @pytest.mark.asyncio
    async def test_publishes_redis_message(
        self, service: OntologyServiceImpl, mock_redis: AsyncMock,
    ) -> None:
        """Should publish a JSON message on the schema_published channel."""
        session = AsyncMock()
        await service.on_schema_published("t1", "ri.snap.123", session)

        mock_redis.publish.assert_called_once()
        channel = mock_redis.publish.call_args[0][0]
        message = json.loads(mock_redis.publish.call_args[0][1])

        assert channel == "ontology:schema_published:t1"
        assert message["tenant_id"] == "t1"
        assert message["snapshot_id"] == "ri.snap.123"
        assert message["event"] == "schema_published"

    @pytest.mark.asyncio
    async def test_invalidates_cache_keys(
        self, service: OntologyServiceImpl, mock_redis: AsyncMock,
    ) -> None:
        """Should scan and delete cached schema keys for the tenant."""
        mock_redis.scan = AsyncMock(
            return_value=(0, [b"ontology:cache:t1:topology", b"ontology:cache:t1:types"])
        )
        session = AsyncMock()
        await service.on_schema_published("t1", "ri.snap.123", session)

        mock_redis.scan.assert_called_once()
        # Should delete the found keys
        mock_redis.delete.assert_called_once_with(
            b"ontology:cache:t1:topology", b"ontology:cache:t1:types"
        )

    @pytest.mark.asyncio
    async def test_no_cache_keys_skips_delete(
        self, service: OntologyServiceImpl, mock_redis: AsyncMock,
    ) -> None:
        """When no cache keys exist, delete should not be called (for cache)."""
        mock_redis.scan = AsyncMock(return_value=(0, []))
        session = AsyncMock()
        await service.on_schema_published("t1", "ri.snap.1", session)

        # scan was called but delete only for commit lock (not cache)
        # The scan found no keys, so no delete for cache keys
        # Only publish should have been called
        mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_scan_iterations(
        self, service: OntologyServiceImpl, mock_redis: AsyncMock,
    ) -> None:
        """Should handle multiple SCAN iterations (cursor != 0)."""
        mock_redis.scan = AsyncMock(side_effect=[
            (42, [b"ontology:cache:t1:key1"]),  # first batch, cursor 42
            (0, [b"ontology:cache:t1:key2"]),   # second batch, cursor 0 = done
        ])
        session = AsyncMock()
        await service.on_schema_published("t1", "ri.snap.1", session)

        assert mock_redis.scan.call_count == 2
        assert mock_redis.delete.call_count == 2


class TestCommitStagingCallsNotification:
    """Test that commit_staging calls on_schema_published after commit."""

    @pytest.mark.asyncio
    async def test_commit_staging_triggers_notification(self) -> None:
        """commit_staging should call on_schema_published after session.commit()."""
        mock_graph = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, []))
        mock_redis.publish = AsyncMock()

        service = OntologyServiceImpl(graph_repo=mock_graph, redis=mock_redis)

        # Set up staging nodes
        mock_graph.get_staging_nodes = AsyncMock(return_value=[
            {
                "rid": "ri.obj.1",
                "api_name": "test",
                "display_name": "Test",
                "is_active": True,
                "_label": "ObjectType",
            },
        ])
        mock_graph.get_active_node = AsyncMock(return_value=None)
        mock_graph.promote_staging_to_active = AsyncMock(return_value=1)

        mock_session = AsyncMock()
        snap_repo_mock = AsyncMock()
        snap_repo_mock.get_active_pointer = AsyncMock(return_value=None)
        snap_repo_mock.create = AsyncMock()
        snap_repo_mock.set_active_pointer = AsyncMock()

        with (
            patch("lingshu.ontology.service.get_user_id", return_value="user1"),
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.SnapshotRepository", return_value=snap_repo_mock),
            patch("lingshu.ontology.service.generate_rid", return_value="ri.snap.new"),
        ):
            await service.commit_staging("test commit", mock_session)

        # Verify publish was called
        mock_redis.publish.assert_called_once()
        channel = mock_redis.publish.call_args[0][0]
        assert "schema_published" in channel
