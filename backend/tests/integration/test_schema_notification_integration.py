"""IT-03: Integration tests for schema publish notification (cache + pub/sub)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from lingshu.ontology.service import OntologyServiceImpl


# ── Helpers ───────────────────────────────────────────────────────


def _build_service() -> tuple[OntologyServiceImpl, AsyncMock, AsyncMock]:
    graph = AsyncMock()
    redis = AsyncMock()
    service = OntologyServiceImpl(graph_repo=graph, redis=redis)
    return service, graph, redis


# ── Tests ─────────────────────────────────────────────────────────


class TestPublishClearsSchemaCache:
    """Publishing schema should delete cached schema keys from Redis."""

    async def test_publish_clears_schema_cache(self) -> None:
        service, graph, redis = _build_service()
        session = AsyncMock()

        # Simulate Redis scan returning cache keys, then empty on second call
        cache_keys = [
            b"ontology:cache:t1:object_types",
            b"ontology:cache:t1:link_types",
            b"ontology:cache:t1:schema_v2",
        ]
        redis.scan = AsyncMock(
            side_effect=[
                (42, cache_keys),  # First scan returns keys with cursor 42
                (0, []),           # Second scan returns cursor 0 (done)
            ]
        )
        redis.delete = AsyncMock()
        redis.publish = AsyncMock()

        await service.on_schema_published("t1", "ri.snap.1", session)

        # Verify cache keys were deleted
        redis.delete.assert_any_await(
            b"ontology:cache:t1:object_types",
            b"ontology:cache:t1:link_types",
            b"ontology:cache:t1:schema_v2",
        )


class TestPublishSendsPubsubEvent:
    """Publishing schema should send pub/sub event with tenant_id and snapshot_id."""

    async def test_publish_sends_pubsub_event(self) -> None:
        service, graph, redis = _build_service()
        session = AsyncMock()

        redis.scan = AsyncMock(return_value=(0, []))
        redis.publish = AsyncMock()

        await service.on_schema_published("t1", "ri.snap.42", session)

        # Verify pub/sub message was sent
        redis.publish.assert_awaited_once()
        call_args = redis.publish.call_args
        channel = call_args[0][0]
        message = json.loads(call_args[0][1])

        assert channel == "ontology:schema_published:t1"
        assert message["tenant_id"] == "t1"
        assert message["snapshot_id"] == "ri.snap.42"
        assert message["event"] == "schema_published"


class TestPublishWithNoCacheKeysSucceeds:
    """Publishing when no cache keys exist should succeed without error."""

    async def test_publish_with_no_cache_keys_succeeds(self) -> None:
        service, graph, redis = _build_service()
        session = AsyncMock()

        # No cache keys found
        redis.scan = AsyncMock(return_value=(0, []))
        redis.publish = AsyncMock()

        # Should not raise
        await service.on_schema_published("t1", "ri.snap.1", session)

        # delete should not have been called (no keys to delete)
        redis.delete.assert_not_awaited()

        # pub/sub should still fire
        redis.publish.assert_awaited_once()
