"""BS-09: Cascade Inheritance with Value Comparison.

Scenario: A data architect modifies SharedPropertyType and verifies
cascade propagation rules: non-overridden properties update,
overridden properties are preserved.

Steps:
1. Create SharedPropertyType
2. Create 2 ObjectTypes with PropertyTypes inheriting from it
3. Override one PropertyType's display_name
4. Update SharedPropertyType
5. Verify cascade: non-overridden updated, overridden kept
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.ontology.service import OntologyServiceImpl
from lingshu.ontology.validators.cascade import cascade_shared_property_update

from .conftest import (
    make_property_type_node,
    make_shared_property_type_node,
    mock_session,
)


def _build_service() -> tuple[OntologyServiceImpl, AsyncMock, AsyncMock]:
    graph = AsyncMock()
    redis = AsyncMock()
    service = OntologyServiceImpl(graph_repo=graph, redis=redis)
    return service, graph, redis


class TestCascadeInheritance:
    """Cascade inheritance and value comparison scenario."""

    async def test_step1_create_shared_property_type(self) -> None:
        """Step 1: Create SharedPropertyType 'common_name'."""
        service, graph, redis = _build_service()

        shprop_node = make_shared_property_type_node(
            "ri.shprop.name", "common_name",
            display_name="Name",
        )
        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(return_value=shprop_node)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.shprop.name",
            ),
        ):
            result = await service.create_shared_property_type({
                "api_name": "common_name",
                "display_name": "Name",
            })
            assert result.rid == "ri.shprop.name"
            assert result.display_name == "Name"

    async def test_cascade_updates_non_overridden(self) -> None:
        """Non-overridden PropertyType follows SharedPropertyType update."""
        graph = AsyncMock()

        # PropertyType A has same display_name as old SharedPropertyType value
        prop_a = make_property_type_node(
            "ri.prop.a", "name_a",
            display_name="Name",  # same as old shared value
            inherit_from_shared_property_type_rid="ri.shprop.name",
        )

        graph.get_related_nodes = AsyncMock(return_value=[prop_a])
        graph.update_node = AsyncMock(return_value={**prop_a, "display_name": "Standard Name"})

        # Cascade: old_values had display_name="Name",
        # updating to display_name="Standard Name"
        await cascade_shared_property_update(
            graph,
            "ri.shprop.name",
            "t1",
            {"display_name": "Standard Name"},
            old_values={"display_name": "Name"},
        )

        # Should have updated prop_a because its value matched old_values
        graph.update_node.assert_awaited()

    async def test_cascade_skips_overridden(self) -> None:
        """Overridden PropertyType does NOT follow SharedPropertyType update."""
        graph = AsyncMock()

        # PropertyType B has custom display_name (overridden)
        prop_b = make_property_type_node(
            "ri.prop.b", "name_b",
            display_name="Custom Name",  # different from old shared value
            inherit_from_shared_property_type_rid="ri.shprop.name",
        )

        graph.get_related_nodes = AsyncMock(return_value=[prop_b])
        graph.update_node = AsyncMock()

        # Cascade: old_values had display_name="Name",
        # updating to display_name="Standard Name"
        # prop_b has "Custom Name" which != "Name", so it should be skipped
        await cascade_shared_property_update(
            graph,
            "ri.shprop.name",
            "t1",
            {"display_name": "Standard Name"},
            old_values={"display_name": "Name"},
        )

        # Should NOT have updated prop_b because its value was overridden
        graph.update_node.assert_not_awaited()

    async def test_cascade_mixed_scenario(self) -> None:
        """Mixed: one property inherits, one overridden."""
        graph = AsyncMock()

        # PropertyType A: inherits (matches old value)
        prop_a = make_property_type_node(
            "ri.prop.a", "name_a",
            display_name="Name",  # matches old
            inherit_from_shared_property_type_rid="ri.shprop.name",
        )

        # PropertyType B: overridden (different from old value)
        prop_b = make_property_type_node(
            "ri.prop.b", "name_b",
            display_name="My Custom Name",  # overridden
            inherit_from_shared_property_type_rid="ri.shprop.name",
        )

        graph.get_related_nodes = AsyncMock(return_value=[prop_a, prop_b])
        graph.update_node = AsyncMock(return_value={**prop_a, "display_name": "Standard Name"})

        await cascade_shared_property_update(
            graph,
            "ri.shprop.name",
            "t1",
            {"display_name": "Standard Name"},
            old_values={"display_name": "Name"},
        )

        # Should have been called once (only for prop_a)
        assert graph.update_node.await_count == 1

    async def test_cascade_through_service(self) -> None:
        """Full cascade through service.update_shared_property_type."""
        service, graph, redis = _build_service()

        old_node = make_shared_property_type_node(
            "ri.shprop.name", "common_name", display_name="Name",
        )
        updated_node = {**old_node, "display_name": "Standard Name", "is_draft": True}

        # Existing inherited PropertyTypes
        prop_inheriting = make_property_type_node(
            "ri.prop.a", "name_a",
            display_name="Name",
            inherit_from_shared_property_type_rid="ri.shprop.name",
        )

        graph.get_active_node = AsyncMock(return_value=old_node)
        redis.get = AsyncMock(return_value=b"u1")
        graph.get_draft_node = AsyncMock(return_value=old_node)
        graph.update_node = AsyncMock(return_value=updated_node)
        graph.get_related_nodes = AsyncMock(return_value=[prop_inheriting])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch(
                "lingshu.ontology.service.check_immutable_fields",
                return_value=None,
            ),
        ):
            result = await service.update_shared_property_type(
                "ri.shprop.name",
                {"display_name": "Standard Name"},
            )
            assert result.rid == "ri.shprop.name"

    async def test_cascade_no_inheriting_properties(self) -> None:
        """Cascade with no inheriting PropertyTypes is a no-op."""
        graph = AsyncMock()
        graph.get_related_nodes = AsyncMock(return_value=[])
        graph.update_node = AsyncMock()

        await cascade_shared_property_update(
            graph,
            "ri.shprop.name",
            "t1",
            {"display_name": "New"},
            old_values={"display_name": "Old"},
        )

        graph.update_node.assert_not_awaited()

    async def test_cascade_non_cascadable_field_ignored(self) -> None:
        """Cascade ignores fields not in CASCADE_FIELDS."""
        graph = AsyncMock()

        prop = make_property_type_node(
            "ri.prop.a", "name_a",
            display_name="Name",
            inherit_from_shared_property_type_rid="ri.shprop.name",
        )
        graph.get_related_nodes = AsyncMock(return_value=[prop])
        graph.update_node = AsyncMock()

        # api_name is not a cascadable field — should be ignored
        await cascade_shared_property_update(
            graph,
            "ri.shprop.name",
            "t1",
            {"api_name": "new_api_name"},
            old_values={"api_name": "old_api_name"},
        )

        graph.update_node.assert_not_awaited()
