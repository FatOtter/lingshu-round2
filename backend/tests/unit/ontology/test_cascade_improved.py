"""Unit tests for T15: SharedPropertyType cascade override detection improvement."""

from unittest.mock import AsyncMock

import pytest

from lingshu.ontology.validators.cascade import CASCADE_FIELDS, cascade_shared_property_update


@pytest.fixture
def mock_graph() -> AsyncMock:
    graph = AsyncMock()
    graph.update_node = AsyncMock(return_value={"rid": "updated"})
    return graph


class TestCascadeValueComparison:
    """Tests for improved cascade using value comparison instead of _override_ flags."""

    @pytest.mark.asyncio
    async def test_cascades_when_values_match_old(self, mock_graph: AsyncMock) -> None:
        """When PropertyType value matches old SharedPropertyType value, cascade should apply."""
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "display_name": "Original Name"},
            {"rid": "ri.prop.2", "display_name": "Original Name"},
        ])

        affected = await cascade_shared_property_update(
            mock_graph,
            "ri.shprop.1",
            "t1",
            {"display_name": "Updated Name"},
            old_values={"display_name": "Original Name"},
        )

        assert len(affected) == 2
        assert mock_graph.update_node.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_when_value_locally_overridden(self, mock_graph: AsyncMock) -> None:
        """When PropertyType has a different value (locally overridden), skip cascade."""
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "display_name": "Custom Name"},  # overridden
            {"rid": "ri.prop.2", "display_name": "Original Name"},  # not overridden
        ])

        affected = await cascade_shared_property_update(
            mock_graph,
            "ri.shprop.1",
            "t1",
            {"display_name": "Updated Name"},
            old_values={"display_name": "Original Name"},
        )

        assert len(affected) == 1
        assert affected[0] == "ri.prop.2"

    @pytest.mark.asyncio
    async def test_cascades_multiple_fields_independently(self, mock_graph: AsyncMock) -> None:
        """Each field should be checked independently for override detection."""
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {
                "rid": "ri.prop.1",
                "display_name": "Original Name",  # matches old → cascade
                "description": "Custom Desc",  # doesn't match old → skip
            },
        ])

        affected = await cascade_shared_property_update(
            mock_graph,
            "ri.shprop.1",
            "t1",
            {"display_name": "New Name", "description": "New Desc"},
            old_values={"display_name": "Original Name", "description": "Original Desc"},
        )

        assert len(affected) == 1
        # Only display_name should be in the update
        call_args = mock_graph.update_node.call_args
        update_dict = call_args[0][3]  # 4th positional arg is properties
        assert "display_name" in update_dict
        assert "description" not in update_dict

    @pytest.mark.asyncio
    async def test_no_old_values_falls_back_to_flag_behavior(self, mock_graph: AsyncMock) -> None:
        """When old_values is None, fall back to _override_ flag checking."""
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "display_name": "anything", "_override_display_name": True},
            {"rid": "ri.prop.2", "display_name": "anything"},
        ])

        affected = await cascade_shared_property_update(
            mock_graph,
            "ri.shprop.1",
            "t1",
            {"display_name": "New Name"},
            old_values=None,
        )

        assert len(affected) == 1
        assert affected[0] == "ri.prop.2"

    @pytest.mark.asyncio
    async def test_no_inheritors_returns_empty(self, mock_graph: AsyncMock) -> None:
        """No inheriting PropertyTypes means empty result."""
        mock_graph.get_related_nodes = AsyncMock(return_value=[])

        affected = await cascade_shared_property_update(
            mock_graph,
            "ri.shprop.1",
            "t1",
            {"display_name": "New"},
            old_values={"display_name": "Old"},
        )

        assert affected == []

    @pytest.mark.asyncio
    async def test_non_cascadable_fields_ignored(self, mock_graph: AsyncMock) -> None:
        """Fields not in CASCADE_FIELDS should not cascade."""
        affected = await cascade_shared_property_update(
            mock_graph,
            "ri.shprop.1",
            "t1",
            {"api_name": "new_api_name", "lifecycle_status": "DEPRECATED"},
            old_values={"api_name": "old_api_name"},
        )

        assert affected == []
        mock_graph.get_related_nodes.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_old_value_comparison(self, mock_graph: AsyncMock) -> None:
        """Value comparison should work correctly when old value is None."""
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "widget": None},  # matches old None
            {"rid": "ri.prop.2", "widget": {"type": "custom"}},  # overridden
        ])

        affected = await cascade_shared_property_update(
            mock_graph,
            "ri.shprop.1",
            "t1",
            {"widget": {"type": "text_input"}},
            old_values={"widget": None},
        )

        assert len(affected) == 1
        assert affected[0] == "ri.prop.1"
