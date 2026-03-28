"""Unit tests for T10: AssetMapping query endpoint."""

from unittest.mock import AsyncMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.service import OntologyServiceImpl


@pytest.fixture
def mock_graph() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_redis() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_graph: AsyncMock, mock_redis: AsyncMock) -> OntologyServiceImpl:
    return OntologyServiceImpl(graph_repo=mock_graph, redis=mock_redis)


def _patch_context(user_id: str = "user1", tenant_id: str = "t1"):
    return (
        patch("lingshu.ontology.service.get_user_id", return_value=user_id),
        patch("lingshu.ontology.service.get_tenant_id", return_value=tenant_id),
    )


class TestQueryAssetMappingReferences:
    """Tests for query_asset_mapping_references."""

    @pytest.mark.asyncio
    async def test_returns_property_types_with_physical_column(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should return PropertyTypes that have physical_column set."""
        mock_graph.get_active_node = AsyncMock(return_value={
            "rid": "ri.obj.1",
            "api_name": "Employee",
            "asset_mapping": {"table": "employees"},
        })
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "api_name": "name", "physical_column": "emp_name"},
            {"rid": "ri.prop.2", "api_name": "age", "physical_column": "emp_age"},
            {"rid": "ri.prop.3", "api_name": "computed", "physical_column": None},
        ])

        with _patch_context()[0], _patch_context()[1]:
            refs = await service.query_asset_mapping_references("ri.obj.1")

        assert len(refs) == 2
        assert refs[0]["rid"] == "ri.prop.1"
        assert refs[0]["physical_column"] == "emp_name"
        assert refs[1]["rid"] == "ri.prop.2"

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_entity(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should raise ONTOLOGY_NOT_FOUND if entity doesn't exist."""
        mock_graph.get_active_node = AsyncMock(return_value=None)

        with _patch_context()[0], _patch_context()[1]:
            with pytest.raises(AppError) as exc_info:
                await service.query_asset_mapping_references("ri.obj.nonexistent")

        assert exc_info.value.code == ErrorCode.ONTOLOGY_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_physical_columns(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should return empty list if no PropertyTypes have physical_column."""
        mock_graph.get_active_node = AsyncMock(return_value={
            "rid": "ri.obj.1", "api_name": "Test",
        })
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "api_name": "virtual_field", "physical_column": None},
        ])

        with _patch_context()[0], _patch_context()[1]:
            refs = await service.query_asset_mapping_references("ri.obj.1")

        assert refs == []

    @pytest.mark.asyncio
    async def test_link_type_entity(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should work with LinkType entities too."""
        mock_graph.get_active_node = AsyncMock(
            side_effect=[None, {"rid": "ri.link.1", "api_name": "manages"}]
        )
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "api_name": "since", "physical_column": "since_date"},
        ])

        with _patch_context()[0], _patch_context()[1]:
            refs = await service.query_asset_mapping_references("ri.link.1")

        assert len(refs) == 1
        assert refs[0]["entity_rid"] == "ri.link.1"

    @pytest.mark.asyncio
    async def test_references_include_entity_rid(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Each reference should include the parent entity_rid."""
        mock_graph.get_active_node = AsyncMock(return_value={
            "rid": "ri.obj.1", "api_name": "Test",
        })
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "api_name": "col1", "physical_column": "c1"},
        ])

        with _patch_context()[0], _patch_context()[1]:
            refs = await service.query_asset_mapping_references("ri.obj.1")

        assert refs[0]["entity_rid"] == "ri.obj.1"
