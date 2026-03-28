"""Unit tests for T2: InterfaceType contract validation."""

from unittest.mock import AsyncMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.validators.contract import (
    _detect_entity_label,
    check_contract_satisfaction,
)


@pytest.fixture
def mock_graph() -> AsyncMock:
    return AsyncMock()


class TestCheckContractSatisfaction:
    """Tests for InterfaceType contract validation."""

    @pytest.mark.asyncio
    async def test_no_required_rids_passes(self, mock_graph: AsyncMock) -> None:
        """Empty required list should always pass."""
        result = await check_contract_satisfaction(
            mock_graph, "ri.iface.1", "t1", []
        )
        assert result == []
        mock_graph.get_related_nodes.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_implementors_passes(self, mock_graph: AsyncMock) -> None:
        """No implementing entities means no violations."""
        mock_graph.get_related_nodes = AsyncMock(return_value=[])
        result = await check_contract_satisfaction(
            mock_graph, "ri.iface.1", "t1", ["ri.shprop.1"]
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_implementor_satisfies_contract(self, mock_graph: AsyncMock) -> None:
        """Implementor with all required PropertyTypes should pass."""
        # First call: get implementors
        # Second call: get PropertyTypes of implementor
        mock_graph.get_related_nodes = AsyncMock(side_effect=[
            [{"rid": "ri.obj.1", "_label": "ObjectType"}],  # implementors
            [{"rid": "ri.prop.1", "inherit_from_shared_property_type_rid": "ri.shprop.1"}],  # property types
        ])

        result = await check_contract_satisfaction(
            mock_graph, "ri.iface.1", "t1", ["ri.shprop.1"]
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_implementor_violates_contract(self, mock_graph: AsyncMock) -> None:
        """Implementor missing required PropertyType should raise AppError."""
        mock_graph.get_related_nodes = AsyncMock(side_effect=[
            [{"rid": "ri.obj.1", "_label": "ObjectType"}],  # implementors
            [{"rid": "ri.prop.1", "inherit_from_shared_property_type_rid": "ri.shprop.2"}],  # wrong shprop
        ])

        with pytest.raises(AppError) as exc_info:
            await check_contract_satisfaction(
                mock_graph, "ri.iface.1", "t1", ["ri.shprop.1"]
            )

        assert exc_info.value.code == ErrorCode.ONTOLOGY_CONTRACT_VIOLATION
        violations = exc_info.value.details["violations"]
        assert len(violations) == 1
        assert violations[0]["entity_rid"] == "ri.obj.1"
        assert "ri.shprop.1" in violations[0]["missing_shared_property_type_rids"]

    @pytest.mark.asyncio
    async def test_multiple_implementors_mixed_violations(self, mock_graph: AsyncMock) -> None:
        """Multiple implementors: some satisfy, some don't."""
        mock_graph.get_related_nodes = AsyncMock(side_effect=[
            [
                {"rid": "ri.obj.1", "_label": "ObjectType"},
                {"rid": "ri.obj.2", "_label": "ObjectType"},
            ],  # implementors
            [{"rid": "ri.prop.1", "inherit_from_shared_property_type_rid": "ri.shprop.1"}],  # obj.1 OK
            [],  # obj.2 has no props → violation
        ])

        with pytest.raises(AppError) as exc_info:
            await check_contract_satisfaction(
                mock_graph, "ri.iface.1", "t1", ["ri.shprop.1"]
            )

        violations = exc_info.value.details["violations"]
        assert len(violations) == 1
        assert violations[0]["entity_rid"] == "ri.obj.2"

    @pytest.mark.asyncio
    async def test_multiple_required_rids(self, mock_graph: AsyncMock) -> None:
        """Validate multiple required SharedPropertyTypes at once."""
        mock_graph.get_related_nodes = AsyncMock(side_effect=[
            [{"rid": "ri.obj.1", "_label": "ObjectType"}],  # implementors
            [
                {"rid": "ri.prop.1", "inherit_from_shared_property_type_rid": "ri.shprop.1"},
                # Missing ri.shprop.2
            ],
        ])

        with pytest.raises(AppError) as exc_info:
            await check_contract_satisfaction(
                mock_graph, "ri.iface.1", "t1", ["ri.shprop.1", "ri.shprop.2"]
            )

        violations = exc_info.value.details["violations"]
        assert "ri.shprop.2" in violations[0]["missing_shared_property_type_rids"]
        assert "ri.shprop.1" not in violations[0]["missing_shared_property_type_rids"]


class TestDetectEntityLabel:
    """Tests for _detect_entity_label helper."""

    def test_uses_label_from_node(self) -> None:
        assert _detect_entity_label({"_label": "LinkType", "rid": "ri.obj.1"}) == "LinkType"

    def test_detects_object_type_from_rid(self) -> None:
        assert _detect_entity_label({"rid": "ri.obj.1"}) == "ObjectType"

    def test_detects_link_type_from_rid(self) -> None:
        assert _detect_entity_label({"rid": "ri.link.1"}) == "LinkType"

    def test_defaults_to_object_type(self) -> None:
        assert _detect_entity_label({"rid": "ri.unknown.1"}) == "ObjectType"
