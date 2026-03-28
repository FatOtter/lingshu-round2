"""Extended tests for OntologyServiceImpl — covering uncovered CRUD, version, lock, and staging methods."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.service import (
    OntologyServiceImpl,
    _deserialize_from_neo4j,
    _node_to_response,
    _node_to_property_response,
    _serialize_for_neo4j,
)


@pytest.fixture
def mock_graph() -> AsyncMock:
    g = AsyncMock()
    g.check_api_name_unique = AsyncMock(return_value=True)
    g.create_node = AsyncMock(return_value={
        "rid": "ri.obj.test1", "api_name": "test_obj", "display_name": "Test",
        "tenant_id": "t1", "is_draft": True, "is_staging": False, "is_active": True,
        "draft_owner": "u1", "created_at": "2025-01-01", "updated_at": "2025-01-01",
    })
    g.get_active_node = AsyncMock(return_value=None)
    g.get_draft_node = AsyncMock(return_value=None)
    g.get_staging_node = AsyncMock(return_value=None)
    g.get_effective_node = AsyncMock(return_value=None)
    g.update_node = AsyncMock(return_value=None)
    g.delete_node = AsyncMock(return_value=True)
    g.list_active_nodes = AsyncMock(return_value=([], 0))
    g.get_related_nodes = AsyncMock(return_value=[])
    g.count_incoming_references = AsyncMock(return_value=0)
    g.create_relationship = AsyncMock(return_value=True)
    g.get_staging_summary = AsyncMock(return_value={})
    g.get_drafts_summary = AsyncMock(return_value={})
    g.get_staging_nodes = AsyncMock(return_value=[])
    g.get_topology = AsyncMock(return_value={"nodes": [], "edges": []})
    g.search_nodes = AsyncMock(return_value=[])
    g.promote_staging_to_active = AsyncMock(return_value=0)
    g.has_uncommitted_changes = AsyncMock(return_value=False)
    return g


@pytest.fixture
def mock_redis() -> AsyncMock:
    r = AsyncMock()
    r.get = AsyncMock(return_value="u1")
    r.set = AsyncMock(return_value=True)
    r.delete = AsyncMock()
    r.expire = AsyncMock()
    r.ttl = AsyncMock(return_value=1800)
    return r


@pytest.fixture
def svc(mock_graph: AsyncMock, mock_redis: AsyncMock) -> OntologyServiceImpl:
    return OntologyServiceImpl(graph_repo=mock_graph, redis=mock_redis)


# ── Serialization helpers ────────────────────────────────────────


class TestSerializeDeserialize:
    def test_serialize_json_fields(self):
        props = {"widget": {"type": "text"}, "api_name": "test"}
        result = _serialize_for_neo4j(props)
        assert isinstance(result["widget"], str)
        assert result["api_name"] == "test"

    def test_deserialize_json_fields(self):
        props = {"widget": '{"type": "text"}', "api_name": "test"}
        result = _deserialize_from_neo4j(props)
        assert result["widget"] == {"type": "text"}
        assert result["api_name"] == "test"

    def test_deserialize_invalid_json(self):
        props = {"widget": "not-json{"}
        result = _deserialize_from_neo4j(props)
        assert result["widget"] == "not-json{"

    def test_deserialize_none_value(self):
        props = {"widget": None}
        result = _deserialize_from_neo4j(props)
        assert result["widget"] is None


class TestNodeToResponse:
    def test_active_status(self):
        node = {"rid": "r1", "api_name": "t", "display_name": "T",
                "is_draft": False, "is_staging": False, "is_active": True}
        resp = _node_to_response(node, "ObjectType")
        assert resp.version_status == "active"

    def test_draft_status(self):
        node = {"rid": "r1", "api_name": "t", "display_name": "T",
                "is_draft": True, "is_staging": False}
        resp = _node_to_response(node, "ObjectType")
        assert resp.version_status == "draft"

    def test_staging_status(self):
        node = {"rid": "r1", "api_name": "t", "display_name": "T",
                "is_draft": False, "is_staging": True}
        resp = _node_to_response(node, "ObjectType")
        assert resp.version_status == "staging"

    def test_unknown_label_uses_entity_response(self):
        node = {"rid": "r1", "api_name": "t", "display_name": "T",
                "is_draft": False, "is_staging": False}
        resp = _node_to_response(node, "UnknownLabel")
        assert resp.rid == "r1"

    def test_property_type_response(self):
        node = {"rid": "r1", "api_name": "prop1", "display_name": "P1",
                "data_type": "string"}
        resp = _node_to_property_response(node)
        assert resp.api_name == "prop1"


# ── Entity CRUD ──────────────────────────────────────────────────


class TestCreateEntity:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_create_object_type(self, mock_uid, mock_tid, svc):
        resp = await svc.create_object_type({"api_name": "test_obj", "display_name": "Test"})
        assert resp.rid == "ri.obj.test1"

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_create_duplicate_api_name(self, mock_uid, mock_tid, svc, mock_graph):
        mock_graph.check_api_name_unique.return_value = False
        with pytest.raises(AppError) as exc_info:
            await svc.create_object_type({"api_name": "taken"})
        assert exc_info.value.code == ErrorCode.ONTOLOGY_DUPLICATE_API_NAME

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_create_link_type(self, mock_uid, mock_tid, svc):
        svc._graph.create_node.return_value = {
            "rid": "ri.link.test1", "api_name": "test_link", "display_name": "Link",
            "tenant_id": "t1", "is_draft": True, "is_staging": False, "is_active": True,
        }
        resp = await svc.create_link_type({"api_name": "test_link", "display_name": "Link"})
        assert "link" in resp.rid

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_create_action_type(self, mock_uid, mock_tid, svc):
        svc._graph.create_node.return_value = {
            "rid": "ri.action.test1", "api_name": "test_action", "display_name": "Action",
            "tenant_id": "t1", "is_draft": True, "is_staging": False, "is_active": True,
        }
        resp = await svc.create_action_type({"api_name": "test_action", "display_name": "Action"})
        assert resp is not None

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_create_shared_property_type(self, mock_uid, mock_tid, svc):
        svc._graph.create_node.return_value = {
            "rid": "ri.shprop.test1", "api_name": "test_sp", "display_name": "SP",
            "tenant_id": "t1", "is_draft": True, "is_staging": False, "is_active": True,
        }
        resp = await svc.create_shared_property_type({"api_name": "test_sp", "display_name": "SP"})
        assert resp is not None

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_create_interface_type_with_extends(self, mock_uid, mock_tid, svc):
        svc._graph.create_node.return_value = {
            "rid": "ri.iface.test1", "api_name": "test_iface", "display_name": "IF",
            "tenant_id": "t1", "is_draft": True, "is_staging": False, "is_active": True,
        }
        # get_related_nodes for cycle check returns empty (no cycle)
        svc._graph.get_related_nodes.return_value = []
        resp = await svc.create_interface_type({
            "api_name": "test_iface", "display_name": "IF",
            "extends_interface_type_rids": ["ri.iface.other"],
        })
        assert resp is not None


class TestGetEntity:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_entity_not_found(self, mock_tid, svc):
        with pytest.raises(AppError) as exc_info:
            await svc._get_entity("ObjectType", "ri.obj.missing")
        assert exc_info.value.code == ErrorCode.ONTOLOGY_NOT_FOUND

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_entity_found(self, mock_tid, svc, mock_graph):
        node = {"rid": "ri.obj.1", "api_name": "t", "display_name": "T",
                "is_draft": False, "is_staging": False, "is_active": True}
        mock_graph.get_active_node.return_value = node
        resp = await svc._get_entity("ObjectType", "ri.obj.1")
        assert resp.rid == "ri.obj.1"

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_entity_with_property_types(self, mock_tid, svc, mock_graph):
        node = {"rid": "ri.obj.1", "api_name": "t", "display_name": "T",
                "is_draft": False, "is_staging": False, "is_active": True}
        pt = {"rid": "ri.prop.1", "api_name": "p1", "display_name": "P1",
              "data_type": "string"}
        mock_graph.get_active_node.return_value = node
        mock_graph.get_related_nodes.return_value = [pt]
        resp = await svc._get_entity("ObjectType", "ri.obj.1")
        assert len(resp.property_types) == 1

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_get_entity_draft_not_found(self, mock_uid, mock_tid, svc):
        with pytest.raises(AppError):
            await svc._get_entity_draft("ObjectType", "ri.obj.missing")

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_get_entity_draft_found(self, mock_uid, mock_tid, svc, mock_graph):
        node = {"rid": "ri.obj.1", "api_name": "t", "display_name": "T",
                "is_draft": True, "is_staging": False}
        mock_graph.get_effective_node.return_value = node
        resp = await svc._get_entity_draft("ObjectType", "ri.obj.1")
        assert resp.version_status == "draft"


class TestUpdateEntity:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_update_existing_draft(self, mock_uid, mock_tid, svc, mock_graph, mock_redis):
        draft = {"rid": "ri.obj.1", "api_name": "t", "display_name": "T",
                 "is_draft": True, "tenant_id": "t1", "is_staging": False}
        mock_graph.get_draft_node.return_value = draft
        mock_graph.update_node.return_value = {**draft, "display_name": "Updated"}
        resp = await svc._update_entity("ObjectType", "ri.obj.1", {"display_name": "Updated"})
        assert resp.display_name == "Updated"

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_update_creates_draft_from_active(self, mock_uid, mock_tid, svc, mock_graph, mock_redis):
        mock_graph.get_draft_node.return_value = None
        mock_graph.get_staging_node.return_value = None
        active = {"rid": "ri.obj.1", "api_name": "t", "display_name": "T",
                  "is_draft": False, "is_staging": False, "is_active": True,
                  "tenant_id": "t1", "snapshot_id": "s1"}
        mock_graph.get_active_node.return_value = active
        mock_graph.create_node.return_value = {**active, "is_draft": True, "display_name": "New"}
        resp = await svc._update_entity("ObjectType", "ri.obj.1", {"display_name": "New"})
        assert resp is not None

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_update_not_found(self, mock_uid, mock_tid, svc, mock_graph, mock_redis):
        mock_graph.get_draft_node.return_value = None
        mock_graph.get_staging_node.return_value = None
        mock_graph.get_active_node.return_value = None
        with pytest.raises(AppError):
            await svc._update_entity("ObjectType", "ri.obj.missing", {"x": 1})

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_update_draft_update_fails(self, mock_uid, mock_tid, svc, mock_graph, mock_redis):
        draft = {"rid": "ri.obj.1", "api_name": "t", "is_draft": True, "tenant_id": "t1"}
        mock_graph.get_draft_node.return_value = draft
        mock_graph.update_node.return_value = None  # update failed
        with pytest.raises(AppError):
            await svc._update_entity("ObjectType", "ri.obj.1", {"x": 1})

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_update_no_lock(self, mock_uid, mock_tid, svc, mock_redis):
        mock_redis.get.return_value = "other_user"
        with pytest.raises(AppError) as exc_info:
            await svc._update_entity("ObjectType", "ri.obj.1", {"x": 1})
        assert exc_info.value.code == ErrorCode.ONTOLOGY_LOCK_REQUIRED


class TestDeleteEntity:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_delete_with_active(self, mock_uid, mock_tid, svc, mock_graph):
        active = {"rid": "ri.obj.1", "is_active": True, "tenant_id": "t1", "snapshot_id": "s1"}
        mock_graph.get_active_node.return_value = active
        await svc._delete_entity("ObjectType", "ri.obj.1")
        mock_graph.create_node.assert_awaited()  # creates deletion marker

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_delete_draft_only(self, mock_uid, mock_tid, svc, mock_graph):
        mock_graph.get_active_node.return_value = None
        mock_graph.delete_node.return_value = True
        await svc._delete_entity("ObjectType", "ri.obj.1")
        mock_graph.delete_node.assert_awaited()

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_delete_falls_to_staging(self, mock_uid, mock_tid, svc, mock_graph):
        mock_graph.get_active_node.return_value = None
        mock_graph.delete_node.side_effect = [False, True]  # first draft fails, then staging
        await svc._delete_entity("ObjectType", "ri.obj.1")
        assert mock_graph.delete_node.await_count == 2


class TestQueryEntities:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_query_empty(self, mock_tid, svc, mock_graph):
        result, total = await svc._query_entities("ObjectType")
        assert total == 0
        assert result == []

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_query_with_results(self, mock_tid, svc, mock_graph):
        nodes = [{"rid": "r1", "api_name": "t", "display_name": "T",
                  "is_draft": False, "is_staging": False, "is_active": True}]
        mock_graph.list_active_nodes.return_value = (nodes, 1)
        result, total = await svc._query_entities("ObjectType", search="t")
        assert total == 1
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_query_with_lifecycle_filter(self, mock_tid, svc, mock_graph):
        mock_graph.list_active_nodes.return_value = ([], 0)
        await svc._query_entities("LinkType", lifecycle_status="active")
        # Verify filters were passed
        call_kwargs = mock_graph.list_active_nodes.call_args[1]
        assert call_kwargs["filters"] == {"lifecycle_status": "active"}


# ── Entity-specific access methods ──────────────────────────────


class TestEntitySpecificMethods:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_object_type(self, mock_tid, svc, mock_graph):
        node = {"rid": "r1"}
        mock_graph.get_active_node.return_value = node
        result = await svc.get_object_type("r1")
        assert result == node

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_link_type(self, mock_tid, svc, mock_graph):
        node = {"rid": "r1"}
        mock_graph.get_active_node.return_value = node
        result = await svc.get_link_type("r1")
        assert result == node

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_object_type_with_explicit_tenant(self, mock_tid, svc, mock_graph):
        node = {"rid": "r1"}
        mock_graph.get_active_node.return_value = node
        result = await svc.get_object_type("r1", tenant_id="custom_tenant")
        mock_graph.get_active_node.assert_awaited_with("ObjectType", "r1", "custom_tenant")

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_query_action_types(self, mock_tid, svc, mock_graph):
        mock_graph.list_active_nodes.return_value = ([], 0)
        result, total = await svc.query_action_types("t1")
        assert total == 0


# ── Lock Management ──────────────────────────────────────────────


class TestLockManagement:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_acquire_lock_success(self, mock_uid, svc, mock_redis):
        mock_redis.set.return_value = True
        resp = await svc.acquire_lock("ri.obj.1")
        assert resp.locked is True
        assert resp.locked_by == "u1"

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_acquire_lock_already_owned(self, mock_uid, svc, mock_redis):
        mock_redis.set.return_value = False  # lock exists
        mock_redis.get.return_value = "u1"  # owned by same user
        resp = await svc.acquire_lock("ri.obj.1")
        assert resp.locked is True

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_acquire_lock_conflict(self, mock_uid, svc, mock_redis):
        mock_redis.set.return_value = False
        mock_redis.get.return_value = "u2"  # other user
        with pytest.raises(AppError) as exc:
            await svc.acquire_lock("ri.obj.1")
        assert exc.value.code == ErrorCode.ONTOLOGY_LOCK_CONFLICT

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_release_lock(self, mock_uid, svc, mock_redis):
        mock_redis.get.return_value = "u1"
        resp = await svc.release_lock("ri.obj.1")
        assert resp.locked is False
        mock_redis.delete.assert_awaited()

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_refresh_lock(self, mock_uid, svc, mock_redis):
        mock_redis.get.return_value = "u1"
        resp = await svc.refresh_lock("ri.obj.1")
        assert resp.locked is True
        mock_redis.expire.assert_awaited()

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_refresh_lock_not_owned(self, mock_uid, svc, mock_redis):
        mock_redis.get.return_value = "u2"
        with pytest.raises(AppError):
            await svc.refresh_lock("ri.obj.1")


# ── Staging / Draft ──────────────────────────────────────────────


class TestStagingDraft:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_submit_to_staging(self, mock_uid, mock_tid, svc, mock_graph, mock_redis):
        draft = {"rid": "r1", "api_name": "t", "is_draft": True, "is_staging": False}
        mock_graph.get_draft_node.return_value = draft
        updated = {"rid": "r1", "api_name": "t", "is_draft": False, "is_staging": True,
                   "display_name": "T"}
        mock_graph.update_node.return_value = updated
        resp = await svc.submit_to_staging("ObjectType", "r1")
        assert resp.version_status == "staging"

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_submit_to_staging_no_draft(self, mock_uid, mock_tid, svc, mock_graph):
        mock_graph.get_draft_node.return_value = None
        with pytest.raises(AppError) as exc:
            await svc.submit_to_staging("ObjectType", "r1")
        assert exc.value.code == ErrorCode.ONTOLOGY_DRAFT_NOT_FOUND

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_submit_to_staging_update_fails(self, mock_uid, mock_tid, svc, mock_graph):
        mock_graph.get_draft_node.return_value = {"rid": "r1"}
        mock_graph.update_node.return_value = None
        with pytest.raises(AppError):
            await svc.submit_to_staging("ObjectType", "r1")

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_discard_draft(self, mock_uid, mock_tid, svc, mock_graph, mock_redis):
        mock_graph.delete_node.return_value = True
        await svc.discard_draft("ObjectType", "r1")
        mock_redis.delete.assert_awaited()

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_discard_draft_not_found(self, mock_uid, mock_tid, svc, mock_graph):
        mock_graph.delete_node.return_value = False
        with pytest.raises(AppError):
            await svc.discard_draft("ObjectType", "r1")

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_discard_staging_with_active(self, mock_tid, svc, mock_graph):
        mock_graph.get_active_node.return_value = {"rid": "r1"}
        mock_graph.delete_node.return_value = True
        await svc.discard_staging("ObjectType", "r1")

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_discard_staging_with_active_not_found(self, mock_tid, svc, mock_graph):
        mock_graph.get_active_node.return_value = {"rid": "r1"}
        mock_graph.delete_node.return_value = False
        with pytest.raises(AppError):
            await svc.discard_staging("ObjectType", "r1")

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_discard_staging_no_active_converts_to_draft(self, mock_uid, mock_tid, svc, mock_graph):
        mock_graph.get_active_node.return_value = None
        staging = {"rid": "r1", "is_staging": True}
        mock_graph.get_staging_node.return_value = staging
        mock_graph.update_node.return_value = {"rid": "r1", "is_draft": True}
        await svc.discard_staging("ObjectType", "r1")
        mock_graph.update_node.assert_awaited()

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_discard_staging_no_active_no_staging(self, mock_tid, svc, mock_graph):
        mock_graph.get_active_node.return_value = None
        mock_graph.get_staging_node.return_value = None
        with pytest.raises(AppError):
            await svc.discard_staging("ObjectType", "r1")


class TestSummaries:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_staging_summary(self, mock_tid, svc, mock_graph):
        mock_graph.get_staging_summary.return_value = {"ObjectType": 2}
        resp = await svc.get_staging_summary()
        assert resp.total == 2
        assert resp.counts == {"ObjectType": 2}

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    @patch("lingshu.ontology.service.get_user_id", return_value="u1")
    async def test_get_drafts_summary(self, mock_uid, mock_tid, svc, mock_graph):
        mock_graph.get_drafts_summary.return_value = {"LinkType": 1}
        resp = await svc.get_drafts_summary()
        assert resp.total == 1


class TestPropertyTypes:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_property_types_for_entity(self, mock_tid, svc, mock_graph):
        pts = [{"rid": "ri.prop.1", "api_name": "p1"}]
        mock_graph.get_related_nodes.return_value = pts
        result = await svc.get_property_types_for_entity("ri.obj.1")
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_property_types_fallback_link(self, mock_tid, svc, mock_graph):
        # First call (ObjectType) returns empty, second (LinkType) returns results
        mock_graph.get_related_nodes.side_effect = [[], [{"rid": "ri.prop.1"}]]
        result = await svc.get_property_types_for_entity("ri.link.1")
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_asset_mapping_not_found(self, mock_tid, svc, mock_graph):
        mock_graph.get_active_node.return_value = None
        result = await svc.get_asset_mapping("ri.obj.missing")
        assert result is None

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_asset_mapping_found(self, mock_tid, svc, mock_graph):
        node = {"rid": "r1", "asset_mapping": '{"table": "users"}'}
        mock_graph.get_active_node.return_value = node
        result = await svc.get_asset_mapping("r1")
        assert result == {"table": "users"}


class TestTopologySearch:
    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_get_topology(self, mock_tid, svc, mock_graph):
        mock_graph.get_topology.return_value = {"nodes": [{"rid": "r1"}], "edges": []}
        resp = await svc.get_topology()
        assert len(resp.nodes) == 1

    @pytest.mark.asyncio
    @patch("lingshu.ontology.service.get_tenant_id", return_value="t1")
    async def test_search_entities(self, mock_tid, svc, mock_graph):
        mock_graph.search_nodes.return_value = [
            {"rid": "r1", "api_name": "test", "_entity_type": "ObjectType",
             "display_name": "Test", "is_draft": False, "is_staging": False},
        ]
        results = await svc.search("test")
        assert len(results) == 1
