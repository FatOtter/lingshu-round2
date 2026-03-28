"""IT-07: Integration tests for cascade update with value comparison."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from lingshu.ontology.validators.cascade import (
    CASCADE_FIELDS,
    cascade_shared_property_update,
)


# ── Helpers ───────────────────────────────────────────────────────


def _make_property_node(
    rid: str,
    display_name: str = "Name",
    description: str = "A property",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "rid": rid,
        "api_name": rid.split(".")[-1],
        "display_name": display_name,
        "description": description,
        "tenant_id": "t1",
        **extra,
    }


# ── Tests ─────────────────────────────────────────────────────────


class TestCascadeUpdatesNonOverridden:
    """PropertyType whose value matches old SharedProperty value should receive cascade."""

    async def test_cascade_updates_non_overridden(self) -> None:
        graph = AsyncMock()

        # PropertyType has display_name == old SharedProperty display_name
        prop_node = _make_property_node(
            "ri.prop.1", display_name="Original Name", description="Original Desc"
        )
        graph.get_related_nodes = AsyncMock(return_value=[prop_node])
        graph.update_node = AsyncMock()

        old_values = {"display_name": "Original Name", "description": "Original Desc"}
        updates = {"display_name": "Updated Name", "description": "Updated Desc"}

        affected = await cascade_shared_property_update(
            graph, "ri.shprop.1", "t1", updates, old_values=old_values
        )

        assert affected == ["ri.prop.1"]
        graph.update_node.assert_awaited_once()
        call_args = graph.update_node.call_args
        assert call_args[0][0] == "PropertyType"
        assert call_args[0][1] == "ri.prop.1"
        update_dict = call_args[0][3]
        assert update_dict["display_name"] == "Updated Name"
        assert update_dict["description"] == "Updated Desc"


class TestCascadeSkipsOverridden:
    """PropertyType whose value differs from old SharedProperty value should be skipped."""

    async def test_cascade_skips_overridden(self) -> None:
        graph = AsyncMock()

        # PropertyType has a custom display_name different from old SharedProperty value
        prop_node = _make_property_node(
            "ri.prop.2",
            display_name="Custom Local Name",
            description="Custom Local Desc",
        )
        graph.get_related_nodes = AsyncMock(return_value=[prop_node])
        graph.update_node = AsyncMock()

        old_values = {"display_name": "Original Name", "description": "Original Desc"}
        updates = {"display_name": "Updated Name", "description": "Updated Desc"}

        affected = await cascade_shared_property_update(
            graph, "ri.shprop.1", "t1", updates, old_values=old_values
        )

        # Both fields were overridden, so nothing should cascade
        assert affected == []
        graph.update_node.assert_not_awaited()


class TestMixedCascade:
    """Some PropertyTypes overridden, some not — correct partial cascade."""

    async def test_mixed_cascade(self) -> None:
        graph = AsyncMock()

        # PropertyType 1: display_name matches old (not overridden),
        #                  description differs (overridden)
        prop_1 = _make_property_node(
            "ri.prop.1",
            display_name="Original Name",
            description="Locally Modified Desc",
        )
        # PropertyType 2: both fields match old (not overridden)
        prop_2 = _make_property_node(
            "ri.prop.2",
            display_name="Original Name",
            description="Original Desc",
        )
        # PropertyType 3: both fields overridden
        prop_3 = _make_property_node(
            "ri.prop.3",
            display_name="Custom Name",
            description="Custom Desc",
        )

        graph.get_related_nodes = AsyncMock(return_value=[prop_1, prop_2, prop_3])
        graph.update_node = AsyncMock()

        old_values = {"display_name": "Original Name", "description": "Original Desc"}
        updates = {"display_name": "New Name", "description": "New Desc"}

        affected = await cascade_shared_property_update(
            graph, "ri.shprop.1", "t1", updates, old_values=old_values
        )

        # prop_1: display_name cascades (matches old), description skipped (overridden)
        # prop_2: both cascade
        # prop_3: both skipped
        assert "ri.prop.1" in affected
        assert "ri.prop.2" in affected
        assert "ri.prop.3" not in affected
        assert len(affected) == 2

        # Verify update calls
        assert graph.update_node.await_count == 2

        # Check prop_1 update: only display_name should cascade
        calls = graph.update_node.call_args_list
        prop_1_call = next(c for c in calls if c[0][1] == "ri.prop.1")
        prop_1_updates = prop_1_call[0][3]
        assert prop_1_updates == {"display_name": "New Name"}

        # Check prop_2 update: both fields should cascade
        prop_2_call = next(c for c in calls if c[0][1] == "ri.prop.2")
        prop_2_updates = prop_2_call[0][3]
        assert prop_2_updates == {"display_name": "New Name", "description": "New Desc"}


class TestCascadeNonCascadableFieldsIgnored:
    """Fields not in CASCADE_FIELDS should be ignored during cascade."""

    async def test_non_cascadable_fields_ignored(self) -> None:
        graph = AsyncMock()

        prop_node = _make_property_node("ri.prop.1", display_name="Original Name")
        graph.get_related_nodes = AsyncMock(return_value=[prop_node])
        graph.update_node = AsyncMock()

        # api_name is not in CASCADE_FIELDS
        updates = {"api_name": "new_api_name", "base_type": "integer"}
        old_values = {"api_name": "old_api_name", "base_type": "string"}

        affected = await cascade_shared_property_update(
            graph, "ri.shprop.1", "t1", updates, old_values=old_values
        )

        assert affected == []
        graph.update_node.assert_not_awaited()


class TestCascadeNoInheritors:
    """Cascade with no inheriting PropertyTypes should return empty list."""

    async def test_cascade_no_inheritors(self) -> None:
        graph = AsyncMock()

        graph.get_related_nodes = AsyncMock(return_value=[])
        graph.update_node = AsyncMock()

        old_values = {"display_name": "Old"}
        updates = {"display_name": "New"}

        affected = await cascade_shared_property_update(
            graph, "ri.shprop.1", "t1", updates, old_values=old_values
        )

        assert affected == []
        graph.update_node.assert_not_awaited()
