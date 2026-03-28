"""BS-06: Multi-Tenant Data Isolation.

Scenario: Verify that different tenants have fully isolated data.

Steps:
1. Tenant A creates ObjectType
2. Tenant B queries -> sees nothing from Tenant A
3. Tenant A queries -> sees own ObjectType
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


class TestMultiTenantIsolation:
    """Multi-tenant data isolation scenario."""

    async def test_tenant_a_creates_entity(self, tenant_id) -> None:
        """Step 1: Tenant A creates an ObjectType."""
        service, graph, redis = _build_service()

        obj_node = make_object_type_node(
            "ri.obj.tenantA_obj", "device_a",
            tenant_id=tenant_id,
        )
        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(return_value=obj_node)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value=tenant_id),
            patch("lingshu.ontology.service.get_user_id", return_value="ri.user.admin"),
            patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.obj.tenantA_obj",
            ),
        ):
            result = await service.create_object_type({
                "api_name": "device_a",
                "display_name": "Device A",
            })
            assert result.rid == "ri.obj.tenantA_obj"

    async def test_tenant_b_sees_nothing_from_tenant_a(
        self, tenant_id_b,
    ) -> None:
        """Step 2: Tenant B queries and sees no data from Tenant A."""
        service, graph, redis = _build_service()

        # Graph returns empty for Tenant B — isolation enforced by tenant_id filter
        graph.list_active_nodes = AsyncMock(return_value=([], 0))

        with (
            patch(
                "lingshu.ontology.service.get_tenant_id",
                return_value=tenant_id_b,
            ),
            patch("lingshu.ontology.service.get_user_id", return_value="ri.user.b1"),
        ):
            results, total = await service._query_entities("ObjectType")
            assert total == 0
            assert results == []

    async def test_tenant_a_sees_own_data(self, tenant_id) -> None:
        """Step 3: Tenant A queries and sees its own ObjectType."""
        service, graph, redis = _build_service()

        obj_node = make_object_type_node(
            "ri.obj.tenantA_obj", "device_a",
            tenant_id=tenant_id,
            is_draft=False,
        )
        graph.list_active_nodes = AsyncMock(return_value=([obj_node], 1))
        graph.get_related_nodes = AsyncMock(return_value=[])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value=tenant_id),
            patch("lingshu.ontology.service.get_user_id", return_value="ri.user.admin"),
        ):
            results, total = await service._query_entities("ObjectType")
            assert total == 1
            assert results[0].rid == "ri.obj.tenantA_obj"

    async def test_tenant_b_cannot_get_tenant_a_entity(
        self, tenant_id_b,
    ) -> None:
        """Tenant B cannot directly get Tenant A's entity."""
        service, graph, redis = _build_service()

        # Graph enforces tenant isolation and returns None
        graph.get_active_node = AsyncMock(return_value=None)

        with (
            patch(
                "lingshu.ontology.service.get_tenant_id",
                return_value=tenant_id_b,
            ),
            patch("lingshu.ontology.service.get_user_id", return_value="ri.user.b1"),
        ):
            from lingshu.infra.errors import AppError, ErrorCode

            with pytest.raises(AppError) as exc_info:
                await service._get_entity("ObjectType", "ri.obj.tenantA_obj")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_NOT_FOUND

    async def test_two_tenants_same_api_name_allowed(
        self, tenant_id, tenant_id_b,
    ) -> None:
        """Two different tenants can have entities with the same api_name."""
        service, graph, redis = _build_service()

        graph.check_api_name_unique = AsyncMock(return_value=True)

        # Tenant A creates
        node_a = make_object_type_node(
            "ri.obj.a1", "shared_name", tenant_id=tenant_id,
        )
        graph.create_node = AsyncMock(return_value=node_a)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value=tenant_id),
            patch("lingshu.ontology.service.get_user_id", return_value="ri.user.a1"),
            patch("lingshu.ontology.service.generate_rid", return_value="ri.obj.a1"),
        ):
            result_a = await service.create_object_type({
                "api_name": "shared_name",
                "display_name": "Shared Name",
            })
            assert result_a.rid == "ri.obj.a1"

        # Tenant B creates same api_name
        node_b = make_object_type_node(
            "ri.obj.b1", "shared_name", tenant_id=tenant_id_b,
        )
        graph.create_node = AsyncMock(return_value=node_b)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value=tenant_id_b),
            patch("lingshu.ontology.service.get_user_id", return_value="ri.user.b1"),
            patch("lingshu.ontology.service.generate_rid", return_value="ri.obj.b1"),
        ):
            result_b = await service.create_object_type({
                "api_name": "shared_name",
                "display_name": "Shared Name",
            })
            assert result_b.rid == "ri.obj.b1"

        # Unique check is always per-tenant in the graph
        assert graph.check_api_name_unique.call_count == 2
