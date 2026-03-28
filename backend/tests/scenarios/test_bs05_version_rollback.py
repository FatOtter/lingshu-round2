"""BS-05: Version Management and Rollback.

Scenario: A data architect publishes changes, discovers a problem,
and rolls back to a previous snapshot.

Steps:
1. Create entity -> publish -> snapshot 1
2. Modify entity -> publish -> snapshot 2
3. Verify field-level diff between snapshots
4. Rollback to snapshot 1
5. Verify entity state matches snapshot 1
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.models import Snapshot
from lingshu.ontology.service import OntologyServiceImpl

from .conftest import (
    make_active_node,
    make_object_type_node,
    make_staging_node,
    mock_session,
)


def _build_service() -> tuple[OntologyServiceImpl, AsyncMock, AsyncMock]:
    graph = AsyncMock()
    redis = AsyncMock()
    service = OntologyServiceImpl(graph_repo=graph, redis=redis)
    return service, graph, redis


class TestVersionRollback:
    """Version management and rollback scenario."""

    async def test_step1_create_and_publish_snapshot1(self) -> None:
        """Step 1: Create entity and publish to get snapshot 1."""
        service, graph, redis = _build_service()
        session = mock_session()

        staging_nodes = [
            make_staging_node(
                make_object_type_node("ri.obj.tl", "traffic_light"),
            ),
        ]

        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        redis.publish = AsyncMock()
        graph.get_staging_nodes = AsyncMock(return_value=staging_nodes)
        graph.get_active_node = AsyncMock(return_value=None)
        graph.promote_staging_to_active = AsyncMock()

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch("lingshu.ontology.service.generate_rid", return_value="ri.snap.v1"),
            patch("lingshu.ontology.service.SnapshotRepository") as MockSnapRepo,
        ):
            MockSnapRepo.return_value.get_active_pointer = AsyncMock(return_value=None)
            MockSnapRepo.return_value.create = AsyncMock()
            MockSnapRepo.return_value.set_active_pointer = AsyncMock()

            snap = await service.commit_staging("Initial version", session)
            assert snap.snapshot_id == "ri.snap.v1"
            assert snap.entity_changes["ri.obj.tl"] == "create"

    async def test_step2_modify_and_publish_snapshot2(self) -> None:
        """Step 2: Modify entity and publish to get snapshot 2."""
        service, graph, redis = _build_service()
        session = mock_session()

        # The modified node now has an extra property
        modified_node = make_staging_node(
            make_object_type_node("ri.obj.tl", "traffic_light"),
        )
        # Simulate an update with added property
        modified_node["description"] = "Updated with maintenance_cycle"

        active_node = make_active_node(
            make_object_type_node("ri.obj.tl", "traffic_light"),
            snapshot_id="ri.snap.v1",
        )

        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        redis.publish = AsyncMock()
        graph.get_staging_nodes = AsyncMock(return_value=[modified_node])
        graph.get_active_node = AsyncMock(return_value=active_node)
        graph.promote_staging_to_active = AsyncMock()

        pointer = MagicMock()
        pointer.snapshot_id = "ri.snap.v1"

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch("lingshu.ontology.service.generate_rid", return_value="ri.snap.v2"),
            patch("lingshu.ontology.service.SnapshotRepository") as MockSnapRepo,
        ):
            MockSnapRepo.return_value.get_active_pointer = AsyncMock(
                return_value=pointer,
            )
            MockSnapRepo.return_value.create = AsyncMock()
            MockSnapRepo.return_value.set_active_pointer = AsyncMock()

            snap = await service.commit_staging("Added maintenance_cycle", session)
            assert snap.snapshot_id == "ri.snap.v2"
            assert snap.parent_snapshot_id == "ri.snap.v1"
            assert snap.entity_changes["ri.obj.tl"] == "update"

    async def test_step3_snapshot_diff(self) -> None:
        """Step 3: Verify field-level diff between snapshots."""
        service, graph, redis = _build_service()
        session = mock_session()

        diff_result = {
            "snapshot_changes": {
                "ri.obj.tl": {
                    "entity_type": "ObjectType",
                    "change_type": "modified",
                    "field_diffs": {
                        "description": {
                            "old_value": "Test traffic_light",
                            "new_value": "Updated with maintenance_cycle",
                        },
                    },
                },
            },
            "current_changes": {},
        }

        pointer = MagicMock()
        pointer.snapshot_id = "ri.snap.v2"

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.SnapshotRepository") as MockSnapRepo,
        ):
            MockSnapRepo.return_value.get_active_pointer = AsyncMock(
                return_value=pointer,
            )
            MockSnapRepo.return_value.get_diff = AsyncMock(return_value=diff_result)

            diff = await service.get_snapshot_diff("ri.snap.v2", session)
            assert "ri.obj.tl" in diff.snapshot_changes
            assert diff.snapshot_changes["ri.obj.tl"]["change_type"] == "modified"

    async def test_step4_rollback_to_snapshot1(self) -> None:
        """Step 4: Rollback to snapshot 1."""
        service, graph, redis = _build_service()
        session = mock_session()

        snap = Snapshot(
            snapshot_id="ri.snap.v1",
            parent_snapshot_id=None,
            tenant_id="t1",
            commit_message="Initial version",
            author="u1",
            entity_changes={"ri.obj.tl": "create"},
        )
        snap.created_at = datetime.now(UTC)

        graph.has_uncommitted_changes = AsyncMock(return_value=False)
        graph.rollback_to_snapshot = AsyncMock()

        pointer = MagicMock()
        pointer.snapshot_id = "ri.snap.v2"

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch("lingshu.ontology.service.SnapshotRepository") as MockSnapRepo,
        ):
            MockSnapRepo.return_value.get_by_id = AsyncMock(return_value=snap)
            MockSnapRepo.return_value.get_active_pointer = AsyncMock(
                return_value=pointer,
            )
            MockSnapRepo.return_value.set_active_pointer = AsyncMock()

            result = await service.rollback_to_snapshot("ri.snap.v1", session)
            assert result.snapshot_id == "ri.snap.v1"
            graph.rollback_to_snapshot.assert_awaited_once_with(
                "t1", "ri.snap.v1", "ri.snap.v2",
            )
            session.commit.assert_awaited()

    async def test_step5_rollback_blocked_with_uncommitted(self) -> None:
        """Step 5: Rollback fails when there are uncommitted changes."""
        service, graph, redis = _build_service()
        session = mock_session()

        graph.has_uncommitted_changes = AsyncMock(return_value=True)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.rollback_to_snapshot("ri.snap.v1", session)
            assert exc_info.value.code == ErrorCode.ONTOLOGY_UNCOMMITTED_CHANGES

    async def test_rollback_snapshot_not_found(self) -> None:
        """Rollback to non-existent snapshot raises error."""
        service, graph, redis = _build_service()
        session = mock_session()

        graph.has_uncommitted_changes = AsyncMock(return_value=False)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch("lingshu.ontology.service.SnapshotRepository") as MockSnapRepo,
        ):
            MockSnapRepo.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.rollback_to_snapshot("ri.snap.missing", session)
            assert exc_info.value.code == ErrorCode.ONTOLOGY_NOT_FOUND

    async def test_query_snapshots(self) -> None:
        """Query snapshot history."""
        service, graph, redis = _build_service()
        session = mock_session()

        snap1 = Snapshot(
            snapshot_id="ri.snap.v1",
            parent_snapshot_id=None,
            tenant_id="t1",
            commit_message="First",
            author="u1",
            entity_changes={},
        )
        snap1.created_at = datetime.now(UTC)

        snap2 = Snapshot(
            snapshot_id="ri.snap.v2",
            parent_snapshot_id="ri.snap.v1",
            tenant_id="t1",
            commit_message="Second",
            author="u1",
            entity_changes={},
        )
        snap2.created_at = datetime.now(UTC)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.SnapshotRepository") as MockSnapRepo,
        ):
            MockSnapRepo.return_value.list_by_tenant = AsyncMock(
                return_value=([snap2, snap1], 2),
            )

            results, total = await service.query_snapshots(session)
            assert total == 2
            assert results[0].snapshot_id == "ri.snap.v2"
            assert results[1].snapshot_id == "ri.snap.v1"

    async def test_commit_staging_empty(self) -> None:
        """Commit with empty staging raises error."""
        service, graph, redis = _build_service()
        session = mock_session()

        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        graph.get_staging_nodes = AsyncMock(return_value=[])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.commit_staging("empty", session)
            assert exc_info.value.code == ErrorCode.ONTOLOGY_STAGING_EMPTY
