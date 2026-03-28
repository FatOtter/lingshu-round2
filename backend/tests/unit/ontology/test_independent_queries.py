"""Unit tests for T12: PropertyType/AssetMapping independent query endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

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


class TestQueryAllPropertyTypes:
    """Tests for query_all_property_types."""

    @pytest.mark.asyncio
    async def test_returns_property_types(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should return PropertyType responses from graph."""
        mock_graph.list_active_nodes = AsyncMock(return_value=(
            [
                {
                    "rid": "ri.prop.1",
                    "api_name": "name",
                    "display_name": "Name",
                    "data_type": "DT_STRING",
                },
                {
                    "rid": "ri.prop.2",
                    "api_name": "age",
                    "display_name": "Age",
                    "data_type": "DT_INTEGER",
                },
            ],
            2,
        ))

        with _patch_context()[0], _patch_context()[1]:
            results, total = await service.query_all_property_types(
                offset=0, limit=20,
            )

        assert total == 2
        assert len(results) == 2
        assert results[0].api_name == "name"
        assert results[1].api_name == "age"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_property_types(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should return empty list when no PropertyTypes exist."""
        mock_graph.list_active_nodes = AsyncMock(return_value=([], 0))

        with _patch_context()[0], _patch_context()[1]:
            results, total = await service.query_all_property_types()

        assert total == 0
        assert results == []

    @pytest.mark.asyncio
    async def test_passes_search_parameter(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Search parameter should be forwarded to graph repo."""
        mock_graph.list_active_nodes = AsyncMock(return_value=([], 0))

        with _patch_context()[0], _patch_context()[1]:
            await service.query_all_property_types(search="email")

        call_kwargs = mock_graph.list_active_nodes.call_args
        assert call_kwargs[1].get("search") == "email" or call_kwargs.kwargs.get("search") == "email"

    @pytest.mark.asyncio
    async def test_pagination_parameters(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Offset and limit should be forwarded."""
        mock_graph.list_active_nodes = AsyncMock(return_value=([], 0))

        with _patch_context()[0], _patch_context()[1]:
            await service.query_all_property_types(offset=10, limit=5)

        mock_graph.list_active_nodes.assert_called_once_with(
            "PropertyType", "t1", offset=10, limit=5, search=None,
        )


class TestQueryAllAssetMappings:
    """Tests for query_all_asset_mappings."""

    @pytest.mark.asyncio
    async def test_returns_entities_with_asset_mapping(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should return only entities that have asset_mapping configured."""
        mock_graph.list_active_nodes = AsyncMock(side_effect=[
            (
                [
                    {
                        "rid": "ri.obj.1",
                        "api_name": "Employee",
                        "display_name": "Employee",
                        "asset_mapping": {"table": "employees"},
                        "is_draft": False,
                        "is_staging": False,
                    },
                    {
                        "rid": "ri.obj.2",
                        "api_name": "Department",
                        "display_name": "Department",
                        "is_draft": False,
                        "is_staging": False,
                    },
                ],
                2,
            ),  # ObjectTypes
            ([], 0),  # LinkTypes
        ])

        with _patch_context()[0], _patch_context()[1]:
            results, total = await service.query_all_asset_mappings()

        assert total == 1
        assert len(results) == 1
        assert results[0]["rid"] == "ri.obj.1"
        assert results[0]["asset_mapping"] == {"table": "employees"}

    @pytest.mark.asyncio
    async def test_includes_link_type_asset_mappings(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should include LinkTypes with asset_mapping too."""
        mock_graph.list_active_nodes = AsyncMock(side_effect=[
            ([], 0),  # ObjectTypes
            (
                [
                    {
                        "rid": "ri.link.1",
                        "api_name": "manages",
                        "display_name": "Manages",
                        "asset_mapping": {"table": "manages_rel"},
                        "is_draft": False,
                        "is_staging": False,
                    },
                ],
                1,
            ),  # LinkTypes
        ])

        with _patch_context()[0], _patch_context()[1]:
            results, total = await service.query_all_asset_mappings()

        assert total == 1
        assert results[0]["rid"] == "ri.link.1"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_asset_mappings(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Should return empty list when no entities have asset_mapping."""
        mock_graph.list_active_nodes = AsyncMock(side_effect=[
            (
                [{"rid": "ri.obj.1", "api_name": "NoMapping", "display_name": "NM", "is_draft": False, "is_staging": False}],
                1,
            ),
            ([], 0),
        ])

        with _patch_context()[0], _patch_context()[1]:
            results, total = await service.query_all_asset_mappings()

        assert total == 0
        assert results == []

    @pytest.mark.asyncio
    async def test_pagination_applied(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Pagination should slice the results correctly."""
        nodes = [
            {
                "rid": f"ri.obj.{i}",
                "api_name": f"type_{i}",
                "display_name": f"Type {i}",
                "asset_mapping": {"table": f"table_{i}"},
                "is_draft": False,
                "is_staging": False,
            }
            for i in range(5)
        ]
        mock_graph.list_active_nodes = AsyncMock(side_effect=[
            (nodes, 5),
            ([], 0),
        ])

        with _patch_context()[0], _patch_context()[1]:
            results, total = await service.query_all_asset_mappings(
                offset=1, limit=2,
            )

        assert total == 5
        assert len(results) == 2
        assert results[0]["rid"] == "ri.obj.1"
        assert results[1]["rid"] == "ri.obj.2"

    @pytest.mark.asyncio
    async def test_result_contains_entity_type(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """Each result should include entity_type field."""
        mock_graph.list_active_nodes = AsyncMock(side_effect=[
            (
                [{
                    "rid": "ri.obj.1",
                    "api_name": "test",
                    "display_name": "Test",
                    "asset_mapping": {"table": "t"},
                    "is_draft": False,
                    "is_staging": False,
                }],
                1,
            ),
            ([], 0),
        ])

        with _patch_context()[0], _patch_context()[1]:
            results, _ = await service.query_all_asset_mappings()

        assert results[0]["entity_type"] == "ObjectType"
