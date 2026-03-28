"""IT-06: Integration tests for AssetMapping reference detection."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.service import OntologyServiceImpl


# ── Helpers ───────────────────────────────────────────────────────


def _make_node(
    rid: str,
    label: str = "ObjectType",
    api_name: str = "robot",
    is_draft: bool = False,
    is_staging: bool = False,
    is_active: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "rid": rid,
        "tenant_id": "t1",
        "api_name": api_name,
        "display_name": api_name.replace("_", " ").title(),
        "description": f"A {api_name}",
        "lifecycle_status": "active",
        "is_draft": is_draft,
        "is_staging": is_staging,
        "is_active": is_active,
        "snapshot_id": None,
        "parent_snapshot_id": None,
        "draft_owner": None,
        "created_at": now,
        "updated_at": now,
        "_label": label,
        **extra,
    }


def _build_service() -> tuple[OntologyServiceImpl, AsyncMock, AsyncMock]:
    graph = AsyncMock()
    redis = AsyncMock()
    service = OntologyServiceImpl(graph_repo=graph, redis=redis)
    return service, graph, redis


# ── Tests ─────────────────────────────────────────────────────────


class TestQueryReferencesReturnsMatchingEntities:
    """query_asset_mapping_references should return PropertyTypes with physical_column."""

    async def test_query_references_returns_matching_entities(self) -> None:
        service, graph, redis = _build_service()

        obj_node = _make_node(
            "ri.obj.1", "ObjectType", "employee",
            asset_mapping={"read_connection_id": "ri.conn.1", "table": "employees"},
        )

        # PropertyTypes belonging to the ObjectType
        prop_with_column = _make_node(
            "ri.prop.1", "PropertyType", "name",
            physical_column="employee_name",
        )
        prop_without_column = _make_node(
            "ri.prop.2", "PropertyType", "virtual_field",
        )

        graph.get_active_node = AsyncMock(return_value=obj_node)
        graph.get_related_nodes = AsyncMock(
            return_value=[prop_with_column, prop_without_column]
        )

        with patch("lingshu.ontology.service.get_tenant_id", return_value="t1"):
            refs = await service.query_asset_mapping_references("ri.obj.1")

        assert len(refs) == 1
        assert refs[0]["rid"] == "ri.prop.1"
        assert refs[0]["physical_column"] == "employee_name"
        assert refs[0]["entity_rid"] == "ri.obj.1"


class TestQueryReferencesReturnsEmptyForNoMatches:
    """query_asset_mapping_references should return empty list when no physical_column."""

    async def test_query_references_returns_empty_for_no_matches(self) -> None:
        service, graph, redis = _build_service()

        obj_node = _make_node(
            "ri.obj.2", "ObjectType", "config",
            asset_mapping={"read_connection_id": "ri.conn.1"},
        )

        # PropertyTypes with no physical_column
        prop_virtual = _make_node("ri.prop.3", "PropertyType", "computed")

        graph.get_active_node = AsyncMock(return_value=obj_node)
        graph.get_related_nodes = AsyncMock(return_value=[prop_virtual])

        with patch("lingshu.ontology.service.get_tenant_id", return_value="t1"):
            refs = await service.query_asset_mapping_references("ri.obj.2")

        assert refs == []


class TestMultipleEntitiesReferenceSameConnection:
    """Multiple ObjectTypes referencing same connection should all be returned by query_all_asset_mappings."""

    async def test_multiple_entities_reference_same_connection(self) -> None:
        service, graph, redis = _build_service()

        obj_a = _make_node(
            "ri.obj.a", "ObjectType", "employee",
            asset_mapping='{"read_connection_id": "ri.conn.1", "table": "employees"}',
        )
        obj_b = _make_node(
            "ri.obj.b", "ObjectType", "department",
            asset_mapping='{"read_connection_id": "ri.conn.1", "table": "departments"}',
        )
        obj_no_mapping = _make_node(
            "ri.obj.c", "ObjectType", "temp",
        )

        graph.list_active_nodes = AsyncMock(
            side_effect=[
                ([obj_a, obj_b, obj_no_mapping], 3),  # ObjectTypes
                ([], 0),                                # LinkTypes
            ]
        )

        with patch("lingshu.ontology.service.get_tenant_id", return_value="t1"):
            results, total = await service.query_all_asset_mappings()

        # Only obj_a and obj_b have asset_mapping
        assert total == 2
        rids = {r["rid"] for r in results}
        assert "ri.obj.a" in rids
        assert "ri.obj.b" in rids
        assert "ri.obj.c" not in rids

        # Both reference the same connection
        for r in results:
            assert r["asset_mapping"]["read_connection_id"] == "ri.conn.1"


class TestQueryReferencesEntityNotFound:
    """query_asset_mapping_references should raise when entity not found."""

    async def test_query_references_entity_not_found(self) -> None:
        service, graph, redis = _build_service()

        graph.get_active_node = AsyncMock(return_value=None)

        with patch("lingshu.ontology.service.get_tenant_id", return_value="t1"):
            with pytest.raises(AppError) as exc_info:
                await service.query_asset_mapping_references("ri.obj.missing")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_NOT_FOUND
