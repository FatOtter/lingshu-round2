"""IT-02: Integration tests for InterfaceType contract validation."""

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
    is_draft: bool = True,
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
        "draft_owner": "u1",
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


class TestPublishFailsWithUnsatisfiedContract:
    """Commit staging should fail when ObjectType does not satisfy InterfaceType contract."""

    async def test_publish_fails_with_unsatisfied_contract(self) -> None:
        service, graph, redis = _build_service()

        # InterfaceType requires SharedPropertyType "ri.shprop.1"
        iface_node = _make_node(
            "ri.iface.1", "InterfaceType", "trackable",
            is_staging=True, is_draft=False,
            required_shared_property_type_rids=["ri.shprop.1"],
        )

        # ObjectType implements the interface but has NO PropertyTypes based on ri.shprop.1
        obj_node = _make_node(
            "ri.obj.1", "ObjectType", "robot",
            is_staging=True, is_draft=False,
            implements_interface_type_rids=["ri.iface.1"],
            _label="ObjectType",
        )

        # update_interface_type calls check_contract_satisfaction when
        # required_shared_property_type_rids is set. Simulate that flow.
        redis.get = AsyncMock(return_value=b"u1")

        # get_related_nodes for IMPLEMENTS → returns the ObjectType
        # get_related_nodes for BELONGS_TO → returns empty (no props)
        async def mock_get_related(label, rid, tenant_id, rel, direction="outgoing"):
            if label == "InterfaceType" and rel == "IMPLEMENTS":
                return [obj_node]
            if rel == "BELONGS_TO":
                return []  # No PropertyTypes → contract violated
            return []

        graph.get_related_nodes = AsyncMock(side_effect=mock_get_related)
        graph.get_draft_node = AsyncMock(return_value=iface_node)
        graph.update_node = AsyncMock(return_value=iface_node)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.update_interface_type(
                    "ri.iface.1",
                    {"required_shared_property_type_rids": ["ri.shprop.1"]},
                )
            assert exc_info.value.code == ErrorCode.ONTOLOGY_CONTRACT_VIOLATION


class TestPublishSucceedsWithSatisfiedContract:
    """Update InterfaceType succeeds when all implementors satisfy contract."""

    async def test_publish_succeeds_with_satisfied_contract(self) -> None:
        service, graph, redis = _build_service()

        iface_node = _make_node(
            "ri.iface.1", "InterfaceType", "trackable",
            required_shared_property_type_rids=["ri.shprop.1"],
        )

        obj_node = _make_node(
            "ri.obj.1", "ObjectType", "robot",
            implements_interface_type_rids=["ri.iface.1"],
            _label="ObjectType",
        )

        # PropertyType that inherits from the required SharedPropertyType
        prop_node = _make_node(
            "ri.prop.1", "PropertyType", "location",
            inherit_from_shared_property_type_rid="ri.shprop.1",
            _label="PropertyType",
        )

        redis.get = AsyncMock(return_value=b"u1")

        async def mock_get_related(label, rid, tenant_id, rel, direction="outgoing"):
            if label == "InterfaceType" and rel == "IMPLEMENTS":
                return [obj_node]
            if label == "ObjectType" and rel == "BELONGS_TO":
                return [prop_node]
            return []

        graph.get_related_nodes = AsyncMock(side_effect=mock_get_related)
        graph.get_draft_node = AsyncMock(return_value=iface_node)
        graph.update_node = AsyncMock(return_value={
            **iface_node,
            "required_shared_property_type_rids": ["ri.shprop.1"],
        })

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            result = await service.update_interface_type(
                "ri.iface.1",
                {"required_shared_property_type_rids": ["ri.shprop.1"]},
            )
            assert result.rid == "ri.iface.1"


class TestUpdateInterfaceAddsRequirementValidatesImplementors:
    """Adding a required prop to InterfaceType validates existing implementors."""

    async def test_update_interface_adds_requirement_validates_implementors(self) -> None:
        service, graph, redis = _build_service()

        iface_node = _make_node("ri.iface.1", "InterfaceType", "auditable")
        obj_node = _make_node("ri.obj.1", "ObjectType", "device", _label="ObjectType")

        # ObjectType has no PropertyTypes based on the new required SharedPropertyType
        async def mock_get_related(label, rid, tenant_id, rel, direction="outgoing"):
            if label == "InterfaceType" and rel == "IMPLEMENTS":
                return [obj_node]
            if rel == "BELONGS_TO":
                return []  # No properties
            return []

        graph.get_related_nodes = AsyncMock(side_effect=mock_get_related)
        redis.get = AsyncMock(return_value=b"u1")

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.update_interface_type(
                    "ri.iface.1",
                    {"required_shared_property_type_rids": ["ri.shprop.new"]},
                )
            assert exc_info.value.code == ErrorCode.ONTOLOGY_CONTRACT_VIOLATION
            assert "1 implementor" in exc_info.value.message


class TestNoImplementorsAllowsAnyContractChange:
    """InterfaceType with no implementors allows any contract change."""

    async def test_no_implementors_allows_any_contract_change(self) -> None:
        service, graph, redis = _build_service()

        iface_node = _make_node("ri.iface.1", "InterfaceType", "disposable")
        updated_node = {
            **iface_node,
            "required_shared_property_type_rids": ["ri.shprop.x", "ri.shprop.y"],
        }

        redis.get = AsyncMock(return_value=b"u1")

        async def mock_get_related(label, rid, tenant_id, rel, direction="outgoing"):
            if label == "InterfaceType" and rel == "IMPLEMENTS":
                return []  # No implementors
            return []

        graph.get_related_nodes = AsyncMock(side_effect=mock_get_related)
        graph.get_draft_node = AsyncMock(return_value=iface_node)
        graph.update_node = AsyncMock(return_value=updated_node)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            result = await service.update_interface_type(
                "ri.iface.1",
                {"required_shared_property_type_rids": ["ri.shprop.x", "ri.shprop.y"]},
            )
            assert result.rid == "ri.iface.1"
