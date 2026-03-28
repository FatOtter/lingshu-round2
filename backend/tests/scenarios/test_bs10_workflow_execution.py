"""BS-10: Workflow Execution.

Scenario: An automation engineer creates and executes a multi-step
workflow with DAG validation and condition branching.

Steps:
1. Create workflow with nodes and edges
2. Validate DAG (no cycles)
3. Execute workflow
4. Verify topological execution order
5. Verify condition branching
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.function.workflows.engine import (
    WorkflowEngine,
    evaluate_condition,
    topological_sort,
)
from lingshu.function.workflows.models import (
    WorkflowDefinition,
    WorkflowEdgeSchema,
    WorkflowNodeSchema,
)
from lingshu.function.schemas.responses import WorkflowResponse
from lingshu.function.workflows.service import WorkflowService
from lingshu.infra.errors import AppError, ErrorCode

from .conftest import mock_session


def _make_node_schema(
    node_id: str,
    node_type: str = "action",
    capability_rid: str = "ri.action.1",
    input_mappings: dict[str, Any] | None = None,
) -> WorkflowNodeSchema:
    return WorkflowNodeSchema(
        node_id=node_id,
        type=node_type,
        capability_rid=capability_rid,
        display_name=f"Node {node_id}",
        input_mappings=input_mappings or {},
    )


def _make_edge_schema(
    source: str,
    target: str,
    condition: str | None = None,
) -> WorkflowEdgeSchema:
    return WorkflowEdgeSchema(
        source_node_id=source,
        target_node_id=target,
        condition=condition,
    )


class TestWorkflowExecution:
    """Workflow execution with DAG validation and condition branching."""

    # ── Step 1: Workflow CRUD ──

    async def test_step1_create_workflow(self) -> None:
        """Step 1: Create a workflow with nodes and edges."""
        service = WorkflowService()
        session = mock_session()

        nodes = [
            {"node_id": "query_faults", "type": "function", "display_name": "Query Faults"},
            {"node_id": "check_count", "type": "condition", "display_name": "Count > 5?"},
            {"node_id": "batch_restart", "type": "action", "display_name": "Batch Restart"},
            {"node_id": "single_restart", "type": "action", "display_name": "Single Restart"},
        ]
        edges = [
            {"source_node_id": "query_faults", "target_node_id": "check_count"},
            {"source_node_id": "check_count", "target_node_id": "batch_restart", "condition": "check_count.result == true"},
            {"source_node_id": "check_count", "target_node_id": "single_restart", "condition": "check_count.result == false"},
        ]

        mock_response = WorkflowResponse(
            rid="ri.workflow.test1",
            api_name="batch_restart_faults",
            display_name="Batch Restart Faults",
            description="Restart all faulty devices",
            nodes=[],
            edges=[],
            safety_level="SAFETY_READ_ONLY",
            status="draft",
            version=1,
            is_active=True,
        )
        # Populate nodes/edges from input for assertion
        mock_response.nodes = [MagicMock(**n) for n in nodes]
        mock_response.edges = [MagicMock(**e) for e in edges]

        with (
            patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.workflows.service.WorkflowRepository") as MockRepo,
            patch.object(WorkflowService, "_to_response", return_value=mock_response),
        ):
            MockRepo.return_value.create = AsyncMock()

            result = await service.create_workflow(
                "batch_restart_faults",
                "Batch Restart Faults",
                "Restart all faulty devices",
                nodes, edges, "draft", session,
            )
            assert result.api_name == "batch_restart_faults"
            assert len(result.nodes) == 4
            assert len(result.edges) == 3

    # ── Step 2: DAG Validation ──

    def test_step2_valid_dag_topological_sort(self) -> None:
        """Step 2: Valid DAG produces correct topological layers."""
        nodes = [
            _make_node_schema("A"),
            _make_node_schema("B"),
            _make_node_schema("C"),
            _make_node_schema("D"),
        ]
        edges = [
            _make_edge_schema("A", "B"),
            _make_edge_schema("A", "C"),
            _make_edge_schema("B", "D"),
            _make_edge_schema("C", "D"),
        ]

        layers = topological_sort(nodes, edges)
        assert layers[0] == ["A"]
        assert set(layers[1]) == {"B", "C"}
        assert layers[2] == ["D"]

    def test_step2_cycle_detection(self) -> None:
        """Step 2: Cyclic graph raises error."""
        nodes = [
            _make_node_schema("A"),
            _make_node_schema("B"),
            _make_node_schema("C"),
        ]
        edges = [
            _make_edge_schema("A", "B"),
            _make_edge_schema("B", "C"),
            _make_edge_schema("C", "A"),
        ]

        with pytest.raises(AppError) as exc_info:
            topological_sort(nodes, edges)
        assert "cycle" in exc_info.value.message.lower()

    def test_step2_linear_dag(self) -> None:
        """Linear DAG produces one node per layer."""
        nodes = [
            _make_node_schema("A"),
            _make_node_schema("B"),
            _make_node_schema("C"),
        ]
        edges = [
            _make_edge_schema("A", "B"),
            _make_edge_schema("B", "C"),
        ]

        layers = topological_sort(nodes, edges)
        assert len(layers) == 3
        assert layers[0] == ["A"]
        assert layers[1] == ["B"]
        assert layers[2] == ["C"]

    def test_step2_parallel_dag(self) -> None:
        """Parallel DAG groups independent nodes in same layer."""
        nodes = [
            _make_node_schema("A"),
            _make_node_schema("B"),
            _make_node_schema("C"),
        ]
        edges: list[WorkflowEdgeSchema] = []

        layers = topological_sort(nodes, edges)
        # All nodes in one layer (no dependencies)
        assert len(layers) == 1
        assert set(layers[0]) == {"A", "B", "C"}

    # ── Step 3: Execute Workflow ──

    async def test_step3_execute_workflow(self) -> None:
        """Step 3: Execute a simple linear workflow."""
        engine = WorkflowEngine()

        definition = WorkflowDefinition(
            nodes=[
                _make_node_schema("step1"),
                _make_node_schema("step2"),
            ],
            edges=[
                _make_edge_schema("step1", "step2"),
            ],
        )

        result = await engine.execute(definition, {"initial": "data"})
        assert result["status"] == "success"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["node_id"] == "step1"
        assert result["steps"][1]["node_id"] == "step2"

    async def test_step3_execute_empty_workflow(self) -> None:
        """Empty workflow completes successfully."""
        engine = WorkflowEngine()
        definition = WorkflowDefinition(nodes=[], edges=[])

        result = await engine.execute(definition, {})
        assert result["status"] == "success"
        assert result["steps"] == []

    # ── Step 4: Topological Execution Order ──

    async def test_step4_parallel_execution(self) -> None:
        """Parallel nodes execute in the same layer."""
        engine = WorkflowEngine()

        definition = WorkflowDefinition(
            nodes=[
                _make_node_schema("root"),
                _make_node_schema("parallel_a"),
                _make_node_schema("parallel_b"),
                _make_node_schema("join"),
            ],
            edges=[
                _make_edge_schema("root", "parallel_a"),
                _make_edge_schema("root", "parallel_b"),
                _make_edge_schema("parallel_a", "join"),
                _make_edge_schema("parallel_b", "join"),
            ],
        )

        result = await engine.execute(definition, {})
        assert result["status"] == "success"
        # root first, then parallel_a and parallel_b, then join
        step_ids = [s["node_id"] for s in result["steps"]]
        assert step_ids[0] == "root"
        assert "join" == step_ids[-1]
        assert set(step_ids[1:3]) == {"parallel_a", "parallel_b"}

    # ── Step 5: Condition Branching ──

    def test_step5_evaluate_condition_true(self) -> None:
        """Condition evaluation returns True."""
        context = {"check_count": {"result": True}}
        assert evaluate_condition("check_count.result == true", context) is True

    def test_step5_evaluate_condition_false(self) -> None:
        """Condition evaluation returns False."""
        context = {"check_count": {"result": False}}
        assert evaluate_condition("check_count.result == true", context) is False

    def test_step5_evaluate_numeric_condition(self) -> None:
        """Numeric condition evaluation."""
        context = {"query": {"data": {"count": 10}}}
        assert evaluate_condition("query.data.count > 5", context) is True
        assert evaluate_condition("query.data.count > 20", context) is False

    def test_step5_evaluate_literal_true(self) -> None:
        """Literal 'true' evaluates to True."""
        assert evaluate_condition("true", {}) is True

    def test_step5_evaluate_literal_false(self) -> None:
        """Literal 'false' evaluates to False."""
        assert evaluate_condition("false", {}) is False

    async def test_step5_conditional_branch_execution(self) -> None:
        """Workflow executes correct branch based on condition."""
        engine = WorkflowEngine()

        definition = WorkflowDefinition(
            nodes=[
                _make_node_schema(
                    "check",
                    node_type="condition",
                    input_mappings={"expression": "_inputs.count > 5"},
                ),
                _make_node_schema("branch_true"),
                _make_node_schema("branch_false"),
            ],
            edges=[
                _make_edge_schema("check", "branch_true", "check.result == true"),
                _make_edge_schema("check", "branch_false", "check.result == false"),
            ],
        )

        # Count > 5 -> branch_true
        result = await engine.execute(definition, {"count": 10})
        step_ids = [s["node_id"] for s in result["steps"]]
        assert "check" in step_ids
        assert "branch_true" in step_ids
        assert "branch_false" not in step_ids

    async def test_workflow_service_execute(self) -> None:
        """Workflow service execute end-to-end."""
        service = WorkflowService()
        session = mock_session()

        workflow = MagicMock()
        workflow.rid = "ri.workflow.w1"
        workflow.definition = {
            "nodes": [
                {"node_id": "n1", "type": "action", "display_name": "N1",
                 "capability_rid": "ri.action.1", "input_mappings": {}},
            ],
            "edges": [],
        }

        with (
            patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.workflows.service.WorkflowRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_rid = AsyncMock(return_value=workflow)

            result = await service.execute_workflow("ri.workflow.w1", {}, session)
            assert result.status == "success"
            assert result.workflow_rid == "ri.workflow.w1"
            assert len(result.steps) == 1

    async def test_workflow_not_found(self) -> None:
        """Execute non-existent workflow raises error."""
        service = WorkflowService()
        session = mock_session()

        with (
            patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.workflows.service.WorkflowRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_rid = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.execute_workflow("ri.workflow.missing", {}, session)
            assert exc_info.value.code == ErrorCode.FUNCTION_NOT_FOUND
