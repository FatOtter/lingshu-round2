"""Extended unit tests for GraphRepository — covering methods not in test_graph_repo.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.ontology.repository.graph_repo import GraphRepository


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


def _setup_single(mock_session: AsyncMock, record: dict | None) -> None:
    result = AsyncMock()
    result.single = AsyncMock(return_value=record)
    mock_session.run = AsyncMock(return_value=result)


def _setup_multi(mock_session: AsyncMock, records: list[dict]) -> None:
    """Setup mock session.run to return async iterable records."""
    result = AsyncMock()

    async def _aiter(*_args, **_kwargs):
        for r in records:
            yield r

    result.__aiter__ = _aiter
    result.single = AsyncMock(return_value=records[0] if records else None)
    mock_session.run = AsyncMock(return_value=result)


class TestGetActiveNode:
    @pytest.mark.asyncio
    async def test_returns_node(self, repo: GraphRepository, mock_session: AsyncMock):
        node = {"rid": "r1", "api_name": "test", "is_active": True}
        _setup_single(mock_session, {"n": node})
        result = await repo.get_active_node("ObjectType", "r1", "t1")
        assert result == node

    @pytest.mark.asyncio
    async def test_returns_none(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, None)
        result = await repo.get_active_node("ObjectType", "r1", "t1")
        assert result is None


class TestGetDraftNode:
    @pytest.mark.asyncio
    async def test_returns_draft(self, repo: GraphRepository, mock_session: AsyncMock):
        node = {"rid": "r1", "is_draft": True, "draft_owner": "u1"}
        _setup_single(mock_session, {"n": node})
        result = await repo.get_draft_node("ObjectType", "r1", "t1", "u1")
        assert result == node

    @pytest.mark.asyncio
    async def test_returns_none(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, None)
        result = await repo.get_draft_node("ObjectType", "r1", "t1", "u1")
        assert result is None


class TestGetStagingNode:
    @pytest.mark.asyncio
    async def test_returns_staging(self, repo: GraphRepository, mock_session: AsyncMock):
        node = {"rid": "r1", "is_staging": True}
        _setup_single(mock_session, {"n": node})
        result = await repo.get_staging_node("ObjectType", "r1", "t1")
        assert result == node


class TestGetEffectiveNode:
    @pytest.mark.asyncio
    async def test_returns_draft_first(self, repo: GraphRepository, mock_session: AsyncMock):
        draft = {"rid": "r1", "is_draft": True}
        _setup_single(mock_session, {"n": draft})
        result = await repo.get_effective_node("ObjectType", "r1", "t1", "u1")
        assert result == draft

    @pytest.mark.asyncio
    async def test_falls_back_to_staging(self, repo: GraphRepository, mock_session: AsyncMock):
        staging = {"rid": "r1", "is_staging": True}
        # First call (draft) returns None, second (staging) returns node
        result_none = AsyncMock()
        result_none.single = AsyncMock(return_value=None)
        result_staging = AsyncMock()
        result_staging.single = AsyncMock(return_value={"n": staging})
        mock_session.run = AsyncMock(side_effect=[result_none, result_staging])

        result = await repo.get_effective_node("ObjectType", "r1", "t1", "u1")
        assert result == staging

    @pytest.mark.asyncio
    async def test_falls_back_to_active(self, repo: GraphRepository, mock_session: AsyncMock):
        active = {"rid": "r1", "is_active": True}
        result_none = AsyncMock()
        result_none.single = AsyncMock(return_value=None)
        result_active = AsyncMock()
        result_active.single = AsyncMock(return_value={"n": active})
        mock_session.run = AsyncMock(side_effect=[result_none, result_none, result_active])

        result = await repo.get_effective_node("ObjectType", "r1", "t1", "u1")
        assert result == active

    @pytest.mark.asyncio
    async def test_returns_none_when_nothing_found(self, repo: GraphRepository, mock_session: AsyncMock):
        result_none = AsyncMock()
        result_none.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=result_none)

        result = await repo.get_effective_node("ObjectType", "r1", "t1", "u1")
        assert result is None


class TestUpdateNode:
    @pytest.mark.asyncio
    async def test_update_basic(self, repo: GraphRepository, mock_session: AsyncMock):
        updated = {"rid": "r1", "display_name": "Updated"}
        _setup_single(mock_session, {"n": updated})
        result = await repo.update_node("ObjectType", "r1", "t1", {"display_name": "Updated"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_with_draft_filter(self, repo: GraphRepository, mock_session: AsyncMock):
        updated = {"rid": "r1", "is_draft": True}
        _setup_single(mock_session, {"n": updated})
        result = await repo.update_node("ObjectType", "r1", "t1", {"x": 1}, is_draft=True, draft_owner="u1")
        assert result == updated
        # Verify the query params included is_draft and draft_owner
        call_kwargs = mock_session.run.call_args[1]
        assert call_kwargs["is_draft"] is True
        assert call_kwargs["draft_owner"] == "u1"

    @pytest.mark.asyncio
    async def test_update_not_found(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, None)
        result = await repo.update_node("ObjectType", "r1", "t1", {"x": 1})
        assert result is None


class TestDeleteNode:
    @pytest.mark.asyncio
    async def test_delete_success(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"deleted": 1})
        result = await repo.delete_node("ObjectType", "r1", "t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"deleted": 0})
        result = await repo.delete_node("ObjectType", "r1", "t1")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_with_draft_staging_filters(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"deleted": 1})
        result = await repo.delete_node("ObjectType", "r1", "t1", is_draft=True, is_staging=False, draft_owner="u1")
        assert result is True
        call_kwargs = mock_session.run.call_args[1]
        assert call_kwargs["is_draft"] is True
        assert call_kwargs["is_staging"] is False
        assert call_kwargs["draft_owner"] == "u1"

    @pytest.mark.asyncio
    async def test_delete_none_record(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, None)
        result = await repo.delete_node("ObjectType", "r1", "t1")
        assert result is False


class TestListActiveNodes:
    @pytest.mark.asyncio
    async def test_list_basic(self, repo: GraphRepository, mock_session: AsyncMock):
        nodes = [{"rid": "r1"}, {"rid": "r2"}]
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 2})
        data_result = AsyncMock()

        async def _aiter(*a, **k):
            for n in nodes:
                yield {"n": n}
        data_result.__aiter__ = _aiter

        mock_session.run = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_active_nodes("ObjectType", "t1")
        assert total == 2
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_with_filters_and_search(self, repo: GraphRepository, mock_session: AsyncMock):
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 1})
        data_result = AsyncMock()

        async def _aiter(*a, **k):
            yield {"n": {"rid": "r1", "api_name": "test"}}
        data_result.__aiter__ = _aiter

        mock_session.run = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_active_nodes(
            "ObjectType", "t1", filters={"status": "active"}, search="test"
        )
        assert total == 1
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_empty(self, repo: GraphRepository, mock_session: AsyncMock):
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 0})
        data_result = AsyncMock()

        async def _aiter(*a, **k):
            return
            yield  # noqa: unreachable

        data_result.__aiter__ = _aiter
        mock_session.run = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_active_nodes("ObjectType", "t1")
        assert total == 0
        assert result == []


class TestRelationships:
    @pytest.mark.asyncio
    async def test_create_relationship_success(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"rel": "HAS_PROPERTY"})
        result = await repo.create_relationship(
            "ObjectType", "r1", "PropertyType", "p1", "HAS_PROPERTY", "t1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_create_relationship_with_props(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"rel": "HAS_PROPERTY"})
        result = await repo.create_relationship(
            "ObjectType", "r1", "PropertyType", "p1", "HAS_PROPERTY", "t1",
            properties={"order": 1},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_create_relationship_fails(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, None)
        result = await repo.create_relationship(
            "ObjectType", "r1", "PropertyType", "p1", "HAS_PROPERTY", "t1",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_relationships_outgoing(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"deleted": 3})
        result = await repo.delete_relationships("ObjectType", "r1", "t1", "HAS_PROP", direction="outgoing")
        assert result == 3

    @pytest.mark.asyncio
    async def test_delete_relationships_incoming(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"deleted": 2})
        result = await repo.delete_relationships("ObjectType", "r1", "t1", "HAS_PROP", direction="incoming")
        assert result == 2

    @pytest.mark.asyncio
    async def test_delete_relationships_both(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"deleted": 5})
        result = await repo.delete_relationships("ObjectType", "r1", "t1", direction="both")
        assert result == 5

    @pytest.mark.asyncio
    async def test_delete_relationships_no_type(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"deleted": 1})
        result = await repo.delete_relationships("ObjectType", "r1", "t1", direction="outgoing")
        assert result == 1

    @pytest.mark.asyncio
    async def test_delete_relationships_none_record(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, None)
        result = await repo.delete_relationships("ObjectType", "r1", "t1")
        assert result == 0


class TestGetRelatedNodes:
    @pytest.mark.asyncio
    async def test_outgoing(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            yield {"m": {"rid": "p1"}}
        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        nodes = await repo.get_related_nodes("ObjectType", "r1", "t1", "HAS_PROP", direction="outgoing")
        assert len(nodes) == 1
        assert nodes[0]["rid"] == "p1"

    @pytest.mark.asyncio
    async def test_incoming(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            yield {"m": {"rid": "o1"}}
        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        nodes = await repo.get_related_nodes("PropertyType", "p1", "t1", "HAS_PROP", direction="incoming")
        assert len(nodes) == 1

    @pytest.mark.asyncio
    async def test_both(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            return
            yield  # noqa
        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        nodes = await repo.get_related_nodes("ObjectType", "r1", "t1", "REL", direction="both")
        assert nodes == []


class TestDependencyChecks:
    @pytest.mark.asyncio
    async def test_count_incoming_with_type(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"cnt": 3})
        result = await repo.count_incoming_references("ObjectType", "r1", "t1", "HAS_PROP")
        assert result == 3

    @pytest.mark.asyncio
    async def test_count_incoming_no_type(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"cnt": 0})
        result = await repo.count_incoming_references("ObjectType", "r1", "t1")
        assert result == 0

    @pytest.mark.asyncio
    async def test_count_incoming_none(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, None)
        result = await repo.count_incoming_references("ObjectType", "r1", "t1")
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_incoming_rids_with_type(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            yield {"rid": "ref1"}
            yield {"rid": "ref2"}
        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        rids = await repo.get_incoming_referencing_rids("ObjectType", "r1", "t1", "HAS_PROP")
        assert rids == ["ref1", "ref2"]

    @pytest.mark.asyncio
    async def test_get_incoming_rids_no_type(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            return
            yield  # noqa
        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        rids = await repo.get_incoming_referencing_rids("ObjectType", "r1", "t1")
        assert rids == []


class TestTopology:
    @pytest.mark.asyncio
    async def test_get_topology(self, repo: GraphRepository, mock_session: AsyncMock):
        nodes_data = [
            {"rid": "r1", "label": "ObjectType", "api_name": "obj1", "display_name": "Object 1"},
        ]
        edges_data = [
            {"source": "r1", "target": "p1", "rel_type": "HAS_PROP"},
        ]

        async def _nodes_iter(*a, **k):
            for n in nodes_data:
                yield n

        async def _edges_iter(*a, **k):
            for e in edges_data:
                yield e

        nodes_result = AsyncMock()
        nodes_result.__aiter__ = _nodes_iter
        edges_result = AsyncMock()
        edges_result.__aiter__ = _edges_iter

        mock_session.run = AsyncMock(side_effect=[nodes_result, edges_result])

        topo = await repo.get_topology("t1")
        assert len(topo["nodes"]) == 1
        assert len(topo["edges"]) == 1


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_nodes(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            yield {"n": {"rid": "r1", "api_name": "test"}, "entity_type": "ObjectType"}

        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        results = await repo.search_nodes("t1", "test")
        assert len(results) == 1
        assert results[0]["_entity_type"] == "ObjectType"

    @pytest.mark.asyncio
    async def test_search_with_labels(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            return
            yield  # noqa

        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        results = await repo.search_nodes("t1", "test", labels=["ObjectType", "LinkType"])
        assert results == []


class TestStagingDraft:
    @pytest.mark.asyncio
    async def test_get_staging_summary(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            yield {"label": "ObjectType", "cnt": 2}
            yield {"label": "LinkType", "cnt": 1}
        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        summary = await repo.get_staging_summary("t1")
        assert summary == {"ObjectType": 2, "LinkType": 1}

    @pytest.mark.asyncio
    async def test_get_staging_nodes(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            yield {"n": {"rid": "r1"}, "label": "ObjectType"}
        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        nodes = await repo.get_staging_nodes("t1")
        assert len(nodes) == 1
        assert nodes[0]["_label"] == "ObjectType"

    @pytest.mark.asyncio
    async def test_get_drafts_summary(self, repo: GraphRepository, mock_session: AsyncMock):
        async def _aiter(*a, **k):
            yield {"label": "ObjectType", "cnt": 3}
        result = AsyncMock()
        result.__aiter__ = _aiter
        mock_session.run = AsyncMock(return_value=result)

        summary = await repo.get_drafts_summary("t1", "u1")
        assert summary == {"ObjectType": 3}


class TestPromoteRollback:
    @pytest.mark.asyncio
    async def test_promote_staging_to_active(self, repo: GraphRepository, mock_session: AsyncMock):
        deactivate_result = AsyncMock()
        promote_result = AsyncMock()
        promote_result.single = AsyncMock(return_value={"promoted": 5})
        cleanup_result = AsyncMock()

        mock_session.run = AsyncMock(side_effect=[deactivate_result, promote_result, cleanup_result])

        count = await repo.promote_staging_to_active("t1", "snap1")
        assert count == 5

    @pytest.mark.asyncio
    async def test_promote_returns_zero_when_none(self, repo: GraphRepository, mock_session: AsyncMock):
        deactivate_result = AsyncMock()
        promote_result = AsyncMock()
        promote_result.single = AsyncMock(return_value=None)
        cleanup_result = AsyncMock()

        mock_session.run = AsyncMock(side_effect=[deactivate_result, promote_result, cleanup_result])

        count = await repo.promote_staging_to_active("t1", "snap1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_rollback_to_snapshot(self, repo: GraphRepository, mock_session: AsyncMock):
        deactivate_result = AsyncMock()
        reactivate_result = AsyncMock()
        reactivate_result.single = AsyncMock(return_value={"reactivated": 3})

        mock_session.run = AsyncMock(side_effect=[deactivate_result, reactivate_result])

        count = await repo.rollback_to_snapshot("t1", "target_snap", "current_snap")
        assert count == 3

    @pytest.mark.asyncio
    async def test_rollback_returns_zero(self, repo: GraphRepository, mock_session: AsyncMock):
        deactivate_result = AsyncMock()
        reactivate_result = AsyncMock()
        reactivate_result.single = AsyncMock(return_value=None)

        mock_session.run = AsyncMock(side_effect=[deactivate_result, reactivate_result])

        count = await repo.rollback_to_snapshot("t1", "target_snap", "current_snap")
        assert count == 0


class TestApiNameUnique:
    @pytest.mark.asyncio
    async def test_unique_returns_true(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"cnt": 0})
        result = await repo.check_api_name_unique("ObjectType", "unique_name", "t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_not_unique_returns_false(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"cnt": 1})
        result = await repo.check_api_name_unique("ObjectType", "taken_name", "t1")
        assert result is False

    @pytest.mark.asyncio
    async def test_with_exclude_rid(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"cnt": 0})
        result = await repo.check_api_name_unique("ObjectType", "name", "t1", exclude_rid="r1")
        assert result is True
        call_kwargs = mock_session.run.call_args[1]
        assert call_kwargs["exclude_rid"] == "r1"


class TestHasUncommittedChanges:
    @pytest.mark.asyncio
    async def test_has_changes(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"cnt": 1})
        assert await repo.has_uncommitted_changes("t1") is True

    @pytest.mark.asyncio
    async def test_no_changes(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, {"cnt": 0})
        assert await repo.has_uncommitted_changes("t1") is False

    @pytest.mark.asyncio
    async def test_none_record(self, repo: GraphRepository, mock_session: AsyncMock):
        _setup_single(mock_session, None)
        assert await repo.has_uncommitted_changes("t1") is False
