"""Unit tests for GraphRepository using mocked Neo4j driver."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.ontology.repository.graph_repo import GraphRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_driver(mock_session: AsyncMock) -> MagicMock:
    """Create a mock driver whose session() returns an async context manager."""
    driver = MagicMock()
    # driver.session() must return an async context manager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = ctx
    return driver


@pytest.fixture
def graph_repo(mock_driver: MagicMock) -> GraphRepository:
    return GraphRepository(mock_driver)


def _setup_single_result(mock_session: AsyncMock, record: dict | None) -> None:
    """Configure mock session.run to return a single record."""
    result = AsyncMock()
    result.single = AsyncMock(return_value=record)
    mock_session.run = AsyncMock(return_value=result)


class TestCreateNode:
    @pytest.mark.asyncio
    async def test_create_node_returns_props(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        props = {"rid": "ri.obj.test", "api_name": "test_obj", "tenant_id": "t1"}
        _setup_single_result(mock_session, {"n": props})

        result = await graph_repo.create_node("ObjectType", props)
        assert result["rid"] == "ri.obj.test"
        assert result["api_name"] == "test_obj"

    @pytest.mark.asyncio
    async def test_create_node_empty_on_failure(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, None)
        result = await graph_repo.create_node("ObjectType", {})
        assert result == {}


class TestGetNode:
    @pytest.mark.asyncio
    async def test_get_active_node(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        node = {"rid": "ri.obj.1", "is_active": True}
        _setup_single_result(mock_session, {"n": node})

        result = await graph_repo.get_active_node("ObjectType", "ri.obj.1", "t1")
        assert result is not None
        assert result["rid"] == "ri.obj.1"

    @pytest.mark.asyncio
    async def test_get_active_node_not_found(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, None)
        result = await graph_repo.get_active_node("ObjectType", "ri.obj.missing", "t1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_draft_node(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        node = {"rid": "ri.obj.1", "is_draft": True, "draft_owner": "user1"}
        _setup_single_result(mock_session, {"n": node})

        result = await graph_repo.get_draft_node("ObjectType", "ri.obj.1", "t1", "user1")
        assert result is not None
        assert result["is_draft"] is True

    @pytest.mark.asyncio
    async def test_get_staging_node(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        node = {"rid": "ri.obj.1", "is_staging": True}
        _setup_single_result(mock_session, {"n": node})

        result = await graph_repo.get_staging_node("ObjectType", "ri.obj.1", "t1")
        assert result is not None
        assert result["is_staging"] is True


class TestDeleteNode:
    @pytest.mark.asyncio
    async def test_delete_returns_true_on_success(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, {"deleted": 1})
        result = await graph_repo.delete_node("ObjectType", "ri.obj.1", "t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_on_miss(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, {"deleted": 0})
        result = await graph_repo.delete_node("ObjectType", "ri.obj.missing", "t1")
        assert result is False


class TestApiNameUnique:
    @pytest.mark.asyncio
    async def test_unique_name(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, {"cnt": 0})
        result = await graph_repo.check_api_name_unique("ObjectType", "test", "t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_duplicate_name(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, {"cnt": 1})
        result = await graph_repo.check_api_name_unique("ObjectType", "test", "t1")
        assert result is False


class TestDependencyCheck:
    @pytest.mark.asyncio
    async def test_count_incoming(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, {"cnt": 3})
        result = await graph_repo.count_incoming_references(
            "ObjectType", "ri.obj.1", "t1", "CONNECTS"
        )
        assert result == 3

    @pytest.mark.asyncio
    async def test_has_uncommitted_true(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, {"cnt": 2})
        result = await graph_repo.has_uncommitted_changes("t1")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_uncommitted_false(
        self, graph_repo: GraphRepository, mock_session: AsyncMock,
    ) -> None:
        _setup_single_result(mock_session, {"cnt": 0})
        result = await graph_repo.has_uncommitted_changes("t1")
        assert result is False
