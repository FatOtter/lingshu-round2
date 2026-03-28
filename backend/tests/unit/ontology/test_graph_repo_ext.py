"""Extended unit tests for GraphRepository — covers methods not in test_graph_repo.py.

Targets: update_node, get_node, get_effective_node, list_active_nodes,
         create_relationship, delete_relationships, get_related_nodes,
         get_incoming_referencing_rids, get_topology, search_nodes,
         get_staging_summary, get_staging_nodes, get_drafts_summary,
         promote_staging_to_active, rollback_to_snapshot.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.ontology.repository.graph_repo import GraphRepository


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_driver(mock_session: AsyncMock) -> MagicMock:
    driver = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = ctx
    return driver


@pytest.fixture
def repo(mock_driver: MagicMock) -> GraphRepository:
    return GraphRepository(mock_driver)


def _single(mock_session: AsyncMock, record: dict | None) -> None:
    """Configure mock session.run to return a single record."""
    result = AsyncMock()
    result.single = AsyncMock(return_value=record)
    mock_session.run = AsyncMock(return_value=result)


class AsyncIterResult:
    """A non-Mock result object that supports async iteration."""

    def __init__(self, records: list[dict]) -> None:
        self._records = records
        self.single = AsyncMock(return_value=None)

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for r in self._records:
            yield r


def _make_async_result(records: list[dict]) -> AsyncIterResult:
    """Create a result that supports async iteration."""
    return AsyncIterResult(records)


def _iter(mock_session: AsyncMock, records: list[dict]) -> None:
    """Configure mock session.run to return iterable records."""
    mock_session.run = AsyncMock(return_value=_make_async_result(records))


# ── get_node ──────────────────────────────────────────────────────


class TestGetNode:
    async def test_get_node_found(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        node = {"rid": "ri.obj.1", "api_name": "Person"}
        _single(mock_session, {"n": node})
        result = await repo.get_node("ObjectType", "ri.obj.1", "t1")
        assert result is not None
        assert result["api_name"] == "Person"

    async def test_get_node_not_found(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, None)
        result = await repo.get_node("ObjectType", "ri.obj.missing", "t1")
        assert result is None


# ── update_node ───────────────────────────────────────────────────


class TestUpdateNode:
    async def test_update_returns_updated(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        updated = {"rid": "ri.obj.1", "display_name": "Updated"}
        _single(mock_session, {"n": updated})
        result = await repo.update_node(
            "ObjectType", "ri.obj.1", "t1", {"display_name": "Updated"}
        )
        assert result is not None
        assert result["display_name"] == "Updated"

    async def test_update_not_found(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, None)
        result = await repo.update_node(
            "ObjectType", "ri.obj.missing", "t1", {"display_name": "X"}
        )
        assert result is None

    async def test_update_with_draft_filter(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        updated = {"rid": "ri.obj.1", "is_draft": True}
        _single(mock_session, {"n": updated})
        result = await repo.update_node(
            "ObjectType",
            "ri.obj.1",
            "t1",
            {"display_name": "Draft Update"},
            is_draft=True,
            draft_owner="user1",
        )
        assert result is not None
        call_kwargs = mock_session.run.call_args
        assert call_kwargs.kwargs["is_draft"] is True
        assert call_kwargs.kwargs["draft_owner"] == "user1"


# ── get_effective_node ────────────────────────────────────────────


class TestGetEffectiveNode:
    async def test_effective_returns_draft_first(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        draft = {"rid": "ri.obj.1", "is_draft": True, "version": "draft"}
        _single(mock_session, {"n": draft})
        result = await repo.get_effective_node(
            "ObjectType", "ri.obj.1", "t1", "user1"
        )
        assert result is not None
        assert result["version"] == "draft"

    async def test_effective_falls_back_to_staging(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        staging = {"rid": "ri.obj.1", "is_staging": True, "version": "staging"}
        results = [AsyncMock(), AsyncMock()]
        results[0].single = AsyncMock(return_value=None)
        results[1].single = AsyncMock(return_value={"n": staging})
        mock_session.run = AsyncMock(side_effect=results)

        result = await repo.get_effective_node(
            "ObjectType", "ri.obj.1", "t1", "user1"
        )
        assert result is not None
        assert result["version"] == "staging"

    async def test_effective_falls_back_to_active(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        active = {"rid": "ri.obj.1", "is_active": True, "version": "active"}
        results = [AsyncMock(), AsyncMock(), AsyncMock()]
        results[0].single = AsyncMock(return_value=None)
        results[1].single = AsyncMock(return_value=None)
        results[2].single = AsyncMock(return_value={"n": active})
        mock_session.run = AsyncMock(side_effect=results)

        result = await repo.get_effective_node(
            "ObjectType", "ri.obj.1", "t1", "user1"
        )
        assert result is not None
        assert result["version"] == "active"


# ── delete_node extended ──────────────────────────────────────────


class TestDeleteNodeExtended:
    async def test_delete_with_draft_filter(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, {"deleted": 1})
        result = await repo.delete_node(
            "ObjectType", "ri.obj.1", "t1", is_draft=True, draft_owner="user1"
        )
        assert result is True
        call_kwargs = mock_session.run.call_args
        assert call_kwargs.kwargs["is_draft"] is True
        assert call_kwargs.kwargs["draft_owner"] == "user1"

    async def test_delete_with_staging_filter(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, {"deleted": 1})
        result = await repo.delete_node(
            "ObjectType", "ri.obj.1", "t1", is_staging=True
        )
        assert result is True
        call_kwargs = mock_session.run.call_args
        assert call_kwargs.kwargs["is_staging"] is True

    async def test_delete_none_record(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, None)
        result = await repo.delete_node("ObjectType", "ri.obj.1", "t1")
        assert result is False


# ── list_active_nodes ─────────────────────────────────────────────


class TestListActiveNodes:
    async def test_list_with_defaults(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 2})
        node1 = {"rid": "ri.obj.1", "api_name": "A"}
        node2 = {"rid": "ri.obj.2", "api_name": "B"}
        data_result = _make_async_result([{"n": node1}, {"n": node2}])
        mock_session.run = AsyncMock(side_effect=[count_result, data_result])

        nodes, total = await repo.list_active_nodes("ObjectType", "t1")
        assert total == 2
        assert len(nodes) == 2
        assert nodes[0]["api_name"] == "A"

    async def test_list_with_filters(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 1})
        data_result = _make_async_result([{"n": {"rid": "ri.obj.1", "status": "active"}}])
        mock_session.run = AsyncMock(side_effect=[count_result, data_result])

        nodes, total = await repo.list_active_nodes(
            "ObjectType", "t1", filters={"status": "active"}
        )
        assert total == 1
        assert len(nodes) == 1

    async def test_list_with_search(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 0})
        data_result = _make_async_result([])
        mock_session.run = AsyncMock(side_effect=[count_result, data_result])

        nodes, total = await repo.list_active_nodes(
            "ObjectType", "t1", search="Person"
        )
        assert total == 0
        assert nodes == []

    async def test_list_empty_count_record(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value=None)
        data_result = _make_async_result([])
        mock_session.run = AsyncMock(side_effect=[count_result, data_result])

        nodes, total = await repo.list_active_nodes("ObjectType", "t1")
        assert total == 0


# ── Relationships ─────────────────────────────────────────────────


class TestCreateRelationship:
    async def test_create_relationship_success(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, {"rel": "HAS_PROPERTY"})
        result = await repo.create_relationship(
            "ObjectType", "ri.obj.1", "PropertyType", "ri.prop.1",
            "HAS_PROPERTY", "t1"
        )
        assert result is True

    async def test_create_relationship_with_properties(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, {"rel": "HAS_PROPERTY"})
        result = await repo.create_relationship(
            "ObjectType", "ri.obj.1", "PropertyType", "ri.prop.1",
            "HAS_PROPERTY", "t1", properties={"order": 1}
        )
        assert result is True

    async def test_create_relationship_no_match(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, None)
        result = await repo.create_relationship(
            "ObjectType", "ri.obj.1", "PropertyType", "ri.prop.missing",
            "HAS_PROPERTY", "t1"
        )
        assert result is False


class TestDeleteRelationships:
    async def test_delete_outgoing(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, {"deleted": 3})
        count = await repo.delete_relationships(
            "ObjectType", "ri.obj.1", "t1", "HAS_PROPERTY", direction="outgoing"
        )
        assert count == 3

    async def test_delete_incoming(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, {"deleted": 1})
        count = await repo.delete_relationships(
            "ObjectType", "ri.obj.1", "t1", "HAS_PROPERTY", direction="incoming"
        )
        assert count == 1

    async def test_delete_both_no_rel_type(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, {"deleted": 5})
        count = await repo.delete_relationships(
            "ObjectType", "ri.obj.1", "t1", direction="both"
        )
        assert count == 5

    async def test_delete_none_record(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, None)
        count = await repo.delete_relationships(
            "ObjectType", "ri.obj.1", "t1", "HAS_PROPERTY"
        )
        assert count == 0


class TestGetRelatedNodes:
    async def test_get_outgoing(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _iter(mock_session, [{"m": {"rid": "ri.prop.1"}}, {"m": {"rid": "ri.prop.2"}}])
        nodes = await repo.get_related_nodes(
            "ObjectType", "ri.obj.1", "t1", "HAS_PROPERTY", direction="outgoing"
        )
        assert len(nodes) == 2

    async def test_get_incoming(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _iter(mock_session, [{"m": {"rid": "ri.obj.1"}}])
        nodes = await repo.get_related_nodes(
            "PropertyType", "ri.prop.1", "t1", "HAS_PROPERTY", direction="incoming"
        )
        assert len(nodes) == 1

    async def test_get_both_directions(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _iter(mock_session, [])
        nodes = await repo.get_related_nodes(
            "ObjectType", "ri.obj.1", "t1", "RELATES_TO", direction="both"
        )
        assert nodes == []


# ── Dependency checks extended ────────────────────────────────────


class TestIncomingReferencingRids:
    async def test_get_rids_with_rel_type(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _iter(mock_session, [{"rid": "ri.link.1"}, {"rid": "ri.link.2"}])
        rids = await repo.get_incoming_referencing_rids(
            "ObjectType", "ri.obj.1", "t1", "CONNECTS"
        )
        assert rids == ["ri.link.1", "ri.link.2"]

    async def test_get_rids_without_rel_type(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _iter(mock_session, [])
        rids = await repo.get_incoming_referencing_rids(
            "ObjectType", "ri.obj.1", "t1"
        )
        assert rids == []

    async def test_count_incoming_no_record(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, None)
        count = await repo.count_incoming_references("ObjectType", "ri.obj.1", "t1")
        assert count == 0


# ── Topology ──────────────────────────────────────────────────────


class TestGetTopology:
    async def test_topology_returns_nodes_and_edges(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        nodes_result = _make_async_result([
            {"rid": "ri.obj.1", "label": "ObjectType", "api_name": "Person", "display_name": "Person"},
        ])
        edges_result = _make_async_result([
            {"source": "ri.obj.1", "target": "ri.link.1", "rel_type": "CONNECTS"},
        ])
        mock_session.run = AsyncMock(side_effect=[nodes_result, edges_result])

        topo = await repo.get_topology("t1")
        assert len(topo["nodes"]) == 1
        assert len(topo["edges"]) == 1
        assert topo["nodes"][0]["rid"] == "ri.obj.1"
        assert topo["edges"][0]["rel_type"] == "CONNECTS"


# ── Search ────────────────────────────────────────────────────────


class TestSearchNodes:
    async def test_search_returns_matching(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        result = _make_async_result([
            {"n": {"rid": "ri.obj.1", "api_name": "Person"}, "entity_type": "ObjectType"},
        ])
        mock_session.run = AsyncMock(return_value=result)

        nodes = await repo.search_nodes("t1", "Person")
        assert len(nodes) == 1
        assert nodes[0]["_entity_type"] == "ObjectType"

    async def test_search_with_label_filter(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        result = _make_async_result([])
        mock_session.run = AsyncMock(return_value=result)

        nodes = await repo.search_nodes(
            "t1", "Person", labels=["ObjectType", "LinkType"]
        )
        assert nodes == []
        mock_session.run.assert_called_once()


# ── Staging/Draft summaries ───────────────────────────────────────


class TestStagingSummary:
    async def test_staging_summary(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _iter(mock_session, [
            {"label": "ObjectType", "cnt": 3},
            {"label": "LinkType", "cnt": 1},
        ])
        summary = await repo.get_staging_summary("t1")
        assert summary == {"ObjectType": 3, "LinkType": 1}


class TestStagingNodes:
    async def test_staging_nodes(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        result = _make_async_result([
            {"n": {"rid": "ri.obj.1", "is_staging": True}, "label": "ObjectType"},
        ])
        mock_session.run = AsyncMock(return_value=result)

        nodes = await repo.get_staging_nodes("t1")
        assert len(nodes) == 1
        assert nodes[0]["_label"] == "ObjectType"


class TestDraftsSummary:
    async def test_drafts_summary(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _iter(mock_session, [{"label": "ObjectType", "cnt": 2}])
        summary = await repo.get_drafts_summary("t1", "user1")
        assert summary == {"ObjectType": 2}


# ── Promote / Rollback ───────────────────────────────────────────


class TestPromoteStagingToActive:
    async def test_promote_returns_count(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        deactivate_result = AsyncMock()
        promote_result = AsyncMock()
        promote_result.single = AsyncMock(return_value={"promoted": 5})
        cleanup_result = AsyncMock()
        mock_session.run = AsyncMock(
            side_effect=[deactivate_result, promote_result, cleanup_result]
        )

        count = await repo.promote_staging_to_active("t1", "ri.snap.1")
        assert count == 5
        assert mock_session.run.call_count == 3

    async def test_promote_none_record(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        deactivate_result = AsyncMock()
        promote_result = AsyncMock()
        promote_result.single = AsyncMock(return_value=None)
        cleanup_result = AsyncMock()
        mock_session.run = AsyncMock(
            side_effect=[deactivate_result, promote_result, cleanup_result]
        )

        count = await repo.promote_staging_to_active("t1", "ri.snap.1")
        assert count == 0


class TestRollbackToSnapshot:
    async def test_rollback_returns_reactivated_count(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        deactivate_result = AsyncMock()
        reactivate_result = AsyncMock()
        reactivate_result.single = AsyncMock(return_value={"reactivated": 8})
        mock_session.run = AsyncMock(
            side_effect=[deactivate_result, reactivate_result]
        )

        count = await repo.rollback_to_snapshot("t1", "ri.snap.old", "ri.snap.current")
        assert count == 8
        assert mock_session.run.call_count == 2

    async def test_rollback_none_record(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        deactivate_result = AsyncMock()
        reactivate_result = AsyncMock()
        reactivate_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(
            side_effect=[deactivate_result, reactivate_result]
        )

        count = await repo.rollback_to_snapshot("t1", "ri.snap.old", "ri.snap.current")
        assert count == 0


# ── check_api_name_unique extended ────────────────────────────────


class TestApiNameUniqueExtended:
    async def test_unique_with_exclude_rid(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, {"cnt": 0})
        result = await repo.check_api_name_unique(
            "ObjectType", "Person", "t1", exclude_rid="ri.obj.1"
        )
        assert result is True
        call_kwargs = mock_session.run.call_args
        assert call_kwargs.kwargs["exclude_rid"] == "ri.obj.1"

    async def test_unique_none_record(
        self, repo: GraphRepository, mock_session: AsyncMock
    ) -> None:
        _single(mock_session, None)
        result = await repo.check_api_name_unique("ObjectType", "Person", "t1")
        assert result is False
