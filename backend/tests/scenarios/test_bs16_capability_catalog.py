"""BS-16: Full Capability Aggregation scenario tests.

Tests the capability catalog: create action types, global functions,
workflows, then query/filter the unified catalog.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.function.schemas.responses import CapabilityDescriptor, FunctionOverviewResponse
from lingshu.function.service import FunctionServiceImpl


def _build_function_service() -> FunctionServiceImpl:
    """Build a FunctionServiceImpl with mocked dependencies."""
    ontology_svc = AsyncMock()
    data_svc = AsyncMock()
    return FunctionServiceImpl(
        ontology_service=ontology_svc,
        data_service=data_svc,
    )


class TestBS16CapabilityCatalog:
    """Capability Aggregation: create capabilities -> list -> filter -> overview."""

    async def test_step1_create_action_type(self) -> None:
        """Create ActionType via ontology (mocked — tested as capability descriptor)."""
        # ActionTypes come from ontology; verified as CapabilityDescriptor
        cap = CapabilityDescriptor(
            type="action",
            rid="ri.action.1",
            api_name="update_robot_position",
            display_name="Update Robot Position",
            description="Updates a robot's position coordinates",
            parameters=[
                {"name": "robot_rid", "type": "object_instance", "required": True},
                {"name": "x", "type": "number", "required": True},
                {"name": "y", "type": "number", "required": True},
            ],
            outputs=[{"name": "position", "type": "object"}],
            safety_level="SAFETY_NON_IDEMPOTENT",
            side_effects=[{"type": "data_mutation", "target": "position"}],
        )
        assert cap.type == "action"
        assert cap.rid == "ri.action.1"
        assert cap.safety_level == "SAFETY_NON_IDEMPOTENT"
        assert len(cap.parameters) == 3

    async def test_step2_create_global_function(
        self, mock_db_session: AsyncMock,
    ) -> None:
        """Create GlobalFunction via function service."""
        service = _build_function_service()

        mock_func = MagicMock()
        mock_func.rid = "ri.func.1"
        mock_func.api_name = "calculate_distance"
        mock_func.display_name = "Calculate Distance"
        mock_func.description = "Calculate Euclidean distance"
        mock_func.parameters = [
            {"name": "x1", "type": "number"},
            {"name": "y1", "type": "number"},
        ]
        mock_func.implementation = {"type": "builtin", "function": "math.distance"}
        mock_func.version = 1
        mock_func.is_active = True
        mock_func.created_at = None
        mock_func.updated_at = None

        with patch.object(
            service._registry, "register", return_value=mock_func,
        ):
            result = await service.create_function(
                api_name="calculate_distance",
                display_name="Calculate Distance",
                description="Calculate Euclidean distance",
                parameters=[{"name": "x1", "type": "number"}],
                implementation={"type": "builtin", "function": "math.distance"},
                session=mock_db_session,
            )
        assert result.rid == "ri.func.1"
        assert result.api_name == "calculate_distance"

    async def test_step3_create_workflow(self) -> None:
        """Create Workflow descriptor (verified as capability)."""
        from lingshu.function.schemas.responses import WorkflowResponse

        workflow = WorkflowResponse(
            rid="ri.workflow.1",
            api_name="data_pipeline",
            display_name="Data Pipeline",
            description="ETL pipeline for data processing",
            nodes=[],
            edges=[],
            safety_level="SAFETY_IDEMPOTENT",
            status="active",
            version=1,
            is_active=True,
        )
        assert workflow.rid == "ri.workflow.1"
        assert workflow.safety_level == "SAFETY_IDEMPOTENT"

    async def test_step4_list_capabilities_all(
        self, mock_db_session: AsyncMock,
    ) -> None:
        """Query capabilities, verify multiple types present."""
        service = _build_function_service()

        func_mock = MagicMock()
        func_mock.rid = "ri.func.1"
        func_mock.api_name = "calc_distance"
        func_mock.display_name = "Calc Distance"
        func_mock.description = "Calculate distance"
        func_mock.parameters = []
        func_mock.is_active = True

        with patch(
            "lingshu.function.service.GlobalFunctionRepository",
        ) as MockFuncRepo, patch(
            "lingshu.function.service.WorkflowRepository",
        ) as MockWfRepo:
            func_repo = MagicMock()
            func_repo.list_by_tenant = AsyncMock(return_value=([func_mock], 1))
            MockFuncRepo.return_value = func_repo

            wf_repo = MagicMock()
            wf_repo.list_by_tenant = AsyncMock(return_value=([], 0))
            MockWfRepo.return_value = wf_repo

            # Mock ontology service for action types
            service._ontology.query_action_types = AsyncMock(return_value=([], 0))

            capabilities = await service.list_capabilities(mock_db_session)

        assert len(capabilities) >= 1
        assert any(c.type == "function" for c in capabilities)

    async def test_step5_filter_by_type(
        self, mock_db_session: AsyncMock,
    ) -> None:
        """Filter by capability_type='function', verify only functions returned."""
        service = _build_function_service()

        func_mock = MagicMock()
        func_mock.rid = "ri.func.2"
        func_mock.api_name = "helper"
        func_mock.display_name = "Helper"
        func_mock.description = "A helper"
        func_mock.parameters = []
        func_mock.is_active = True

        with patch(
            "lingshu.function.service.GlobalFunctionRepository",
        ) as MockRepo:
            repo_instance = MagicMock()
            repo_instance.list_by_tenant = AsyncMock(return_value=([func_mock], 1))
            MockRepo.return_value = repo_instance

            capabilities = await service.list_capabilities(
                mock_db_session, capability_type="function",
            )

        for cap in capabilities:
            assert cap.type == "function"

    async def test_step6_overview_real_counts(
        self, mock_db_session: AsyncMock,
    ) -> None:
        """Get overview, verify capability counts structure."""
        service = _build_function_service()

        with patch(
            "lingshu.function.service.GlobalFunctionRepository",
        ) as MockFuncRepo, patch(
            "lingshu.function.service.ExecutionRepository",
        ) as MockExecRepo, patch(
            "lingshu.function.service.WorkflowRepository",
        ) as MockWfRepo:
            func_repo = MagicMock()
            func_repo.count_by_tenant = AsyncMock(return_value=3)
            MockFuncRepo.return_value = func_repo

            exec_repo = MagicMock()
            exec_repo.count_recent = AsyncMock(return_value={"success": 5, "failed": 1})
            MockExecRepo.return_value = exec_repo

            wf_repo = MagicMock()
            wf_repo.count_by_tenant = AsyncMock(return_value=2)
            MockWfRepo.return_value = wf_repo

            # Mock ontology service for action count
            service._ontology.query_action_types = AsyncMock(return_value=([], 4))

            overview = await service.get_overview(mock_db_session)

        assert overview.capabilities["functions"] == 3
        assert overview.capabilities["workflows"] == 2
        assert overview.capabilities["actions"] == 4
        assert overview.recent_executions["total_24h"] == 6
        assert overview.recent_executions["by_status"]["success"] == 5
