"""Unit tests for Ontology validators: dependency, cascade, cycle detection."""

from unittest.mock import AsyncMock

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.validators.cascade import cascade_shared_property_update
from lingshu.ontology.validators.cycle_detection import check_interface_cycle
from lingshu.ontology.validators.dependency import check_delete_dependencies


@pytest.fixture
def mock_graph() -> AsyncMock:
    return AsyncMock()


class TestDependencyCheck:
    @pytest.mark.asyncio
    async def test_no_deps_allows_delete(self, mock_graph: AsyncMock) -> None:
        mock_graph.get_incoming_referencing_rids = AsyncMock(return_value=[])
        # Should not raise
        await check_delete_dependencies(
            mock_graph, "SharedPropertyType", "ri.shprop.1", "t1"
        )

    @pytest.mark.asyncio
    async def test_with_deps_raises_conflict(self, mock_graph: AsyncMock) -> None:
        mock_graph.get_incoming_referencing_rids = AsyncMock(
            side_effect=[
                ["ri.prop.1", "ri.prop.2"],  # BASED_ON
                [],  # REQUIRES
            ]
        )
        with pytest.raises(AppError) as exc_info:
            await check_delete_dependencies(
                mock_graph, "SharedPropertyType", "ri.shprop.1", "t1"
            )
        assert exc_info.value.code == ErrorCode.ONTOLOGY_DEPENDENCY_CONFLICT

    @pytest.mark.asyncio
    async def test_action_type_always_deletable(self, mock_graph: AsyncMock) -> None:
        # ActionType has no dependency rules
        await check_delete_dependencies(
            mock_graph, "ActionType", "ri.action.1", "t1"
        )
        mock_graph.get_incoming_referencing_rids.assert_not_called()


class TestCycleDetection:
    @pytest.mark.asyncio
    async def test_no_cycle(self, mock_graph: AsyncMock) -> None:
        # A extends B, B has no outgoing EXTENDS
        mock_graph.get_related_nodes = AsyncMock(return_value=[])
        await check_interface_cycle(
            mock_graph, "ri.iface.A", ["ri.iface.B"], "t1"
        )

    @pytest.mark.asyncio
    async def test_direct_cycle_detected(self, mock_graph: AsyncMock) -> None:
        # A extends B, B extends A → cycle
        async def mock_get_related(label: str, rid: str, tenant_id: str, rel_type: str, *, direction: str = "outgoing") -> list[dict]:
            if rid == "ri.iface.B":
                return [{"rid": "ri.iface.A"}]
            return []

        mock_graph.get_related_nodes = mock_get_related

        with pytest.raises(AppError) as exc_info:
            await check_interface_cycle(
                mock_graph, "ri.iface.A", ["ri.iface.B"], "t1"
            )
        assert exc_info.value.code == ErrorCode.ONTOLOGY_CYCLE_DETECTED

    @pytest.mark.asyncio
    async def test_indirect_cycle_detected(self, mock_graph: AsyncMock) -> None:
        # A extends B, B extends C, C extends A → cycle
        async def mock_get_related(label: str, rid: str, tenant_id: str, rel_type: str, *, direction: str = "outgoing") -> list[dict]:
            if rid == "ri.iface.B":
                return [{"rid": "ri.iface.C"}]
            if rid == "ri.iface.C":
                return [{"rid": "ri.iface.A"}]
            return []

        mock_graph.get_related_nodes = mock_get_related

        with pytest.raises(AppError) as exc_info:
            await check_interface_cycle(
                mock_graph, "ri.iface.A", ["ri.iface.B"], "t1"
            )
        assert exc_info.value.code == ErrorCode.ONTOLOGY_CYCLE_DETECTED

    @pytest.mark.asyncio
    async def test_empty_extends_skips(self, mock_graph: AsyncMock) -> None:
        await check_interface_cycle(mock_graph, "ri.iface.A", [], "t1")
        mock_graph.get_related_nodes.assert_not_called()


class TestCascadeUpdate:
    @pytest.mark.asyncio
    async def test_cascades_display_name(self, mock_graph: AsyncMock) -> None:
        mock_graph.get_related_nodes = AsyncMock(return_value=[
            {"rid": "ri.prop.1", "display_name": "old_name"},
            {"rid": "ri.prop.2", "display_name": "old_name"},
        ])
        mock_graph.update_node = AsyncMock(return_value={"rid": "ri.prop.1"})

        affected = await cascade_shared_property_update(
            mock_graph, "ri.shprop.1", "t1",
            {"display_name": "new_name"},
        )
        assert len(affected) == 2

    @pytest.mark.asyncio
    async def test_non_cascadable_field_ignored(self, mock_graph: AsyncMock) -> None:
        affected = await cascade_shared_property_update(
            mock_graph, "ri.shprop.1", "t1",
            {"api_name": "changed"},  # Not cascadable
        )
        assert affected == []
        mock_graph.get_related_nodes.assert_not_called()
