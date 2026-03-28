"""Unit tests for OntologyServiceImpl."""

from unittest.mock import AsyncMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.service import OntologyServiceImpl, _node_to_response


@pytest.fixture
def mock_graph() -> AsyncMock:
    graph = AsyncMock()
    graph.check_api_name_unique = AsyncMock(return_value=True)
    graph.create_node = AsyncMock(return_value={
        "rid": "ri.obj.test-uuid",
        "api_name": "test_obj",
        "display_name": "Test Object",
        "tenant_id": "t1",
        "is_draft": True,
        "is_staging": False,
        "is_active": True,
        "draft_owner": "user1",
    })
    return graph


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"user1")
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    redis.expire = AsyncMock()
    redis.ttl = AsyncMock(return_value=1800)
    return redis


@pytest.fixture
def service(mock_graph: AsyncMock, mock_redis: AsyncMock) -> OntologyServiceImpl:
    return OntologyServiceImpl(graph_repo=mock_graph, redis=mock_redis)


def _patch_context(user_id: str = "user1", tenant_id: str = "t1"):
    """Helper to patch ContextVar getters."""
    return (
        patch("lingshu.ontology.service.get_user_id", return_value=user_id),
        patch("lingshu.ontology.service.get_tenant_id", return_value=tenant_id),
    )


class TestNodeToResponse:
    def test_active_version_status(self) -> None:
        node = {
            "rid": "ri.obj.1", "api_name": "test", "display_name": "Test",
            "is_draft": False, "is_staging": False, "is_active": True,
        }
        resp = _node_to_response(node, "ObjectType")
        assert resp.version_status == "active"

    def test_draft_version_status(self) -> None:
        node = {
            "rid": "ri.obj.1", "api_name": "test", "display_name": "Test",
            "is_draft": True, "is_staging": False, "is_active": True,
        }
        resp = _node_to_response(node, "ObjectType")
        assert resp.version_status == "draft"

    def test_staging_version_status(self) -> None:
        node = {
            "rid": "ri.obj.1", "api_name": "test", "display_name": "Test",
            "is_draft": False, "is_staging": True, "is_active": True,
        }
        resp = _node_to_response(node, "ObjectType")
        assert resp.version_status == "staging"


class TestCreateEntity:
    @pytest.mark.asyncio
    async def test_create_object_type(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        p1, p2 = _patch_context()
        with p1, p2:
            result = await service.create_object_type({
                "api_name": "test_obj",
                "display_name": "Test Object",
            })
        assert result.api_name == "test_obj"
        assert result.version_status == "draft"
        mock_graph.check_api_name_unique.assert_called_once()
        mock_graph.create_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_duplicate_api_name_raises(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.check_api_name_unique = AsyncMock(return_value=False)
        p1, p2 = _patch_context()
        with p1, p2:
            with pytest.raises(AppError) as exc_info:
                await service.create_object_type({
                    "api_name": "existing",
                    "display_name": "Dup",
                })
            assert exc_info.value.code == ErrorCode.ONTOLOGY_DUPLICATE_API_NAME


class TestGetEntity:
    @pytest.mark.asyncio
    async def test_get_existing(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.get_active_node = AsyncMock(return_value={
            "rid": "ri.obj.1", "api_name": "test", "display_name": "Test",
            "is_draft": False, "is_staging": False, "is_active": True,
        })
        p1, p2 = _patch_context()
        with p1, p2:
            result = await service._get_entity("ObjectType", "ri.obj.1")
        assert result.rid == "ri.obj.1"

    @pytest.mark.asyncio
    async def test_get_not_found(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.get_active_node = AsyncMock(return_value=None)
        p1, p2 = _patch_context()
        with p1, p2:
            with pytest.raises(AppError) as exc_info:
                await service._get_entity("ObjectType", "ri.obj.missing")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_NOT_FOUND


class TestLockManagement:
    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, service: OntologyServiceImpl, mock_redis: AsyncMock) -> None:
        p1, p2 = _patch_context()
        with p1, p2:
            result = await service.acquire_lock("ri.obj.1")
        assert result.locked is True
        assert result.locked_by == "user1"

    @pytest.mark.asyncio
    async def test_acquire_lock_conflict(self, service: OntologyServiceImpl, mock_redis: AsyncMock) -> None:
        mock_redis.set = AsyncMock(return_value=False)
        mock_redis.get = AsyncMock(return_value=b"other_user")
        p1, p2 = _patch_context()
        with p1, p2:
            with pytest.raises(AppError) as exc_info:
                await service.acquire_lock("ri.obj.1")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_LOCK_CONFLICT

    @pytest.mark.asyncio
    async def test_release_lock(self, service: OntologyServiceImpl, mock_redis: AsyncMock) -> None:
        p1, p2 = _patch_context()
        with p1, p2:
            result = await service.release_lock("ri.obj.1")
        assert result.locked is False

    @pytest.mark.asyncio
    async def test_refresh_lock(self, service: OntologyServiceImpl, mock_redis: AsyncMock) -> None:
        p1, p2 = _patch_context()
        with p1, p2:
            result = await service.refresh_lock("ri.obj.1")
        assert result.locked is True
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_lock_not_owner(self, service: OntologyServiceImpl, mock_redis: AsyncMock) -> None:
        mock_redis.get = AsyncMock(return_value=b"other_user")
        p1, p2 = _patch_context()
        with p1, p2:
            with pytest.raises(AppError) as exc_info:
                await service.refresh_lock("ri.obj.1")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_LOCK_CONFLICT


class TestSubmitToStaging:
    @pytest.mark.asyncio
    async def test_submit_success(self, service: OntologyServiceImpl, mock_graph: AsyncMock, mock_redis: AsyncMock) -> None:
        mock_graph.get_draft_node = AsyncMock(return_value={
            "rid": "ri.obj.1", "api_name": "test", "display_name": "Test",
            "is_draft": True, "is_staging": False, "is_active": True,
        })
        mock_graph.update_node = AsyncMock(return_value={
            "rid": "ri.obj.1", "api_name": "test", "display_name": "Test",
            "is_draft": False, "is_staging": True, "is_active": True,
        })
        p1, p2 = _patch_context()
        with p1, p2:
            result = await service.submit_to_staging("ObjectType", "ri.obj.1")
        assert result.version_status == "staging"

    @pytest.mark.asyncio
    async def test_submit_no_draft_raises(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.get_draft_node = AsyncMock(return_value=None)
        p1, p2 = _patch_context()
        with p1, p2:
            with pytest.raises(AppError) as exc_info:
                await service.submit_to_staging("ObjectType", "ri.obj.1")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_DRAFT_NOT_FOUND


class TestDiscardDraft:
    @pytest.mark.asyncio
    async def test_discard_success(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.delete_node = AsyncMock(return_value=True)
        p1, p2 = _patch_context()
        with p1, p2:
            await service.discard_draft("ObjectType", "ri.obj.1")

    @pytest.mark.asyncio
    async def test_discard_not_found(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.delete_node = AsyncMock(return_value=False)
        p1, p2 = _patch_context()
        with p1, p2:
            with pytest.raises(AppError) as exc_info:
                await service.discard_draft("ObjectType", "ri.obj.1")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_DRAFT_NOT_FOUND


class TestStagingSummary:
    @pytest.mark.asyncio
    async def test_staging_summary(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.get_staging_summary = AsyncMock(return_value={"ObjectType": 2, "LinkType": 1})
        p1, p2 = _patch_context()
        with p1, p2:
            result = await service.get_staging_summary()
        assert result.total == 3
        assert result.counts["ObjectType"] == 2

    @pytest.mark.asyncio
    async def test_drafts_summary(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.get_drafts_summary = AsyncMock(return_value={"ObjectType": 1})
        p1, p2 = _patch_context()
        with p1, p2:
            result = await service.get_drafts_summary()
        assert result.total == 1


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_with_uncommitted_changes_raises(self, service: OntologyServiceImpl, mock_graph: AsyncMock) -> None:
        mock_graph.has_uncommitted_changes = AsyncMock(return_value=True)
        p1, p2 = _patch_context()
        with p1, p2:
            with pytest.raises(AppError) as exc_info:
                session = AsyncMock()
                await service.rollback_to_snapshot("ri.snap.1", session)
            assert exc_info.value.code == ErrorCode.ONTOLOGY_UNCOMMITTED_CHANGES
