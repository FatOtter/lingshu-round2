"""BS-11: Data Search, Filtering, and Pagination.

Scenario: A business analyst searches and filters data through
various query combinations.

Steps:
1. Query with search term -> filter applied
2. Query with sort -> order correct
3. Query with pagination -> correct page
4. Combined filter + sort + pagination
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from lingshu.ontology.service import OntologyServiceImpl

from .conftest import make_object_type_node


def _build_service() -> tuple[OntologyServiceImpl, AsyncMock, AsyncMock]:
    graph = AsyncMock()
    redis = AsyncMock()
    service = OntologyServiceImpl(graph_repo=graph, redis=redis)
    return service, graph, redis


class TestDataSearchFilter:
    """Data search, filtering, and pagination scenario."""

    async def test_step1_search_by_term(self) -> None:
        """Step 1: Query with search term filters results."""
        service, graph, redis = _build_service()

        matching_node = make_object_type_node(
            "ri.obj.tl", "traffic_light", display_name="Traffic Light",
        )
        graph.list_active_nodes = AsyncMock(return_value=([matching_node], 1))
        graph.get_related_nodes = AsyncMock(return_value=[])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            results, total = await service._query_entities(
                "ObjectType", search="traffic",
            )
            assert total == 1
            assert results[0].api_name == "traffic_light"

            # Verify search was passed to graph
            graph.list_active_nodes.assert_awaited_once()
            call_kwargs = graph.list_active_nodes.call_args
            assert call_kwargs.kwargs.get("search") == "traffic"

    async def test_step1_search_no_results(self) -> None:
        """Step 1: Search with no matching results returns empty."""
        service, graph, redis = _build_service()

        graph.list_active_nodes = AsyncMock(return_value=([], 0))

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            results, total = await service._query_entities(
                "ObjectType", search="nonexistent_term",
            )
            assert total == 0
            assert results == []

    async def test_step2_query_with_pagination(self) -> None:
        """Step 2: Query with pagination returns correct page."""
        service, graph, redis = _build_service()

        # Page 2 of results
        node = make_object_type_node("ri.obj.page2", "entity_21")
        graph.list_active_nodes = AsyncMock(return_value=([node], 30))
        graph.get_related_nodes = AsyncMock(return_value=[])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            results, total = await service._query_entities(
                "ObjectType", offset=20, limit=10,
            )
            assert total == 30  # total count across all pages
            assert len(results) == 1  # this page has 1 result

            call_kwargs = graph.list_active_nodes.call_args
            assert call_kwargs.kwargs.get("offset") == 20
            assert call_kwargs.kwargs.get("limit") == 10

    async def test_step3_query_with_lifecycle_filter(self) -> None:
        """Step 3: Query with lifecycle status filter."""
        service, graph, redis = _build_service()

        active_node = make_object_type_node(
            "ri.obj.active1", "active_entity", is_draft=False,
        )
        graph.list_active_nodes = AsyncMock(return_value=([active_node], 1))
        graph.get_related_nodes = AsyncMock(return_value=[])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            results, total = await service._query_entities(
                "ObjectType", lifecycle_status="active",
            )
            assert total == 1

            call_kwargs = graph.list_active_nodes.call_args
            filters = call_kwargs.kwargs.get("filters")
            assert filters is not None
            assert filters.get("lifecycle_status") == "active"

    async def test_step4_combined_search_and_pagination(self) -> None:
        """Step 4: Combined search + pagination."""
        service, graph, redis = _build_service()

        nodes = [
            make_object_type_node(f"ri.obj.t{i}", f"traffic_{i}")
            for i in range(5)
        ]
        graph.list_active_nodes = AsyncMock(return_value=(nodes, 15))
        graph.get_related_nodes = AsyncMock(return_value=[])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            results, total = await service._query_entities(
                "ObjectType",
                search="traffic",
                offset=0,
                limit=5,
            )
            assert total == 15
            assert len(results) == 5

            call_kwargs = graph.list_active_nodes.call_args
            assert call_kwargs.kwargs.get("search") == "traffic"
            assert call_kwargs.kwargs.get("offset") == 0
            assert call_kwargs.kwargs.get("limit") == 5

    async def test_ontology_search_api(self) -> None:
        """Test the ontology search API."""
        service, graph, redis = _build_service()

        search_nodes = [
            {
                "rid": "ri.obj.tl",
                "api_name": "traffic_light",
                "display_name": "Traffic Light",
                "description": "A traffic signal",
                "_entity_type": "ObjectType",
            },
            {
                "rid": "ri.link.mon",
                "api_name": "monitoring_range",
                "display_name": "Monitoring Range",
                "description": "Camera monitoring",
                "_entity_type": "LinkType",
            },
        ]
        graph.search_nodes = AsyncMock(return_value=search_nodes)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
        ):
            results = await service.search("traffic")
            assert len(results) == 2
            assert results[0].rid == "ri.obj.tl"
            assert results[1].entity_type == "LinkType"

    async def test_ontology_search_with_type_filter(self) -> None:
        """Search with entity type filter."""
        service, graph, redis = _build_service()

        search_nodes = [
            {
                "rid": "ri.obj.tl",
                "api_name": "traffic_light",
                "display_name": "Traffic Light",
                "description": "",
                "_entity_type": "ObjectType",
            },
        ]
        graph.search_nodes = AsyncMock(return_value=search_nodes)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
        ):
            results = await service.search(
                "traffic", types=["object_type"], limit=10,
            )
            assert len(results) == 1

            call_kwargs = graph.search_nodes.call_args
            assert call_kwargs.kwargs.get("limit") == 10

    async def test_query_all_property_types(self) -> None:
        """Query all PropertyTypes across entities."""
        service, graph, redis = _build_service()

        from .conftest import make_property_type_node

        props = [
            make_property_type_node("ri.prop.1", "name", base_type="string"),
            make_property_type_node("ri.prop.2", "status", base_type="integer"),
        ]
        graph.list_active_nodes = AsyncMock(return_value=(props, 2))

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
        ):
            results, total = await service.query_all_property_types()
            assert total == 2
            assert len(results) == 2

    async def test_query_all_asset_mappings(self) -> None:
        """Query all entities with asset_mapping configured."""
        service, graph, redis = _build_service()

        obj_with_mapping = make_object_type_node(
            "ri.obj.mapped", "mapped_type",
            asset_mapping='{"read_connection_id":"ri.conn.pg1"}',
        )
        obj_without_mapping = make_object_type_node(
            "ri.obj.unmapped", "unmapped_type",
        )

        graph.list_active_nodes = AsyncMock(
            side_effect=[
                ([obj_with_mapping, obj_without_mapping], 2),
                ([], 0),
            ],
        )

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
        ):
            results, total = await service.query_all_asset_mappings()
            assert total == 1  # only the one with mapping
            assert results[0]["rid"] == "ri.obj.mapped"
