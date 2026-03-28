"""Unit tests for the workflow engine: DAG sort, execution, conditions, safety."""

import asyncio

import pytest

from lingshu.function.workflows.engine import (
    WorkflowEngine,
    compute_safety_level,
    evaluate_condition,
    topological_sort,
)
from lingshu.function.workflows.models import (
    WorkflowDefinition,
    WorkflowEdgeSchema,
    WorkflowNodeSchema,
)
from lingshu.infra.errors import AppError


# ── Helpers ──────────────────────────────────────────────────────

def _node(node_id: str, ntype: str = "action", **kwargs):
    return WorkflowNodeSchema(node_id=node_id, type=ntype, **kwargs)


def _edge(src: str, tgt: str, condition: str | None = None):
    return WorkflowEdgeSchema(
        source_node_id=src, target_node_id=tgt, condition=condition,
    )


# ── Topological Sort ────────────────────────────────────────────

class TestTopologicalSort:
    def test_linear_chain(self) -> None:
        nodes = [_node("a"), _node("b"), _node("c")]
        edges = [_edge("a", "b"), _edge("b", "c")]
        layers = topological_sort(nodes, edges)
        assert layers == [["a"], ["b"], ["c"]]

    def test_parallel_roots(self) -> None:
        nodes = [_node("a"), _node("b"), _node("c")]
        edges = [_edge("a", "c"), _edge("b", "c")]
        layers = topological_sort(nodes, edges)
        assert layers == [["a", "b"], ["c"]]

    def test_diamond_dag(self) -> None:
        nodes = [_node("a"), _node("b"), _node("c"), _node("d")]
        edges = [
            _edge("a", "b"), _edge("a", "c"),
            _edge("b", "d"), _edge("c", "d"),
        ]
        layers = topological_sort(nodes, edges)
        assert layers == [["a"], ["b", "c"], ["d"]]

    def test_single_node(self) -> None:
        nodes = [_node("only")]
        layers = topological_sort(nodes, [])
        assert layers == [["only"]]

    def test_cycle_detected(self) -> None:
        nodes = [_node("a"), _node("b")]
        edges = [_edge("a", "b"), _edge("b", "a")]
        with pytest.raises(AppError, match="cycle"):
            topological_sort(nodes, edges)

    def test_empty_graph(self) -> None:
        layers = topological_sort([], [])
        assert layers == []


# ── Condition Evaluation ────────────────────────────────────────

class TestConditionEvaluation:
    def test_true_literal(self) -> None:
        assert evaluate_condition("true", {}) is True

    def test_false_literal(self) -> None:
        assert evaluate_condition("false", {}) is False

    def test_equality(self) -> None:
        ctx = {"node_a": {"status": "ok"}}
        assert evaluate_condition("node_a.status == ok", ctx) is True
        assert evaluate_condition("node_a.status == fail", ctx) is False

    def test_numeric_comparison(self) -> None:
        ctx = {"node_a": {"count": 5}}
        assert evaluate_condition("node_a.count > 3", ctx) is True
        assert evaluate_condition("node_a.count < 3", ctx) is False
        assert evaluate_condition("node_a.count >= 5", ctx) is True

    def test_not_equal(self) -> None:
        ctx = {"node_a": {"val": 10}}
        assert evaluate_condition("node_a.val != 20", ctx) is True
        assert evaluate_condition("node_a.val != 10", ctx) is False


# ── Safety Level Computation ────────────────────────────────────

class TestSafetyLevel:
    def test_empty_defaults_to_read_only(self) -> None:
        assert compute_safety_level([]) == "SAFETY_READ_ONLY"

    def test_max_level_wins(self) -> None:
        levels = ["SAFETY_READ_ONLY", "SAFETY_CRITICAL", "SAFETY_IDEMPOTENT_WRITE"]
        assert compute_safety_level(levels) == "SAFETY_CRITICAL"

    def test_single_level(self) -> None:
        assert compute_safety_level(["SAFETY_NON_IDEMPOTENT"]) == "SAFETY_NON_IDEMPOTENT"


# ── Engine Execution ────────────────────────────────────────────

class TestWorkflowEngine:
    @pytest.mark.asyncio
    async def test_sequential_execution(self) -> None:
        definition = WorkflowDefinition(
            nodes=[_node("a"), _node("b")],
            edges=[_edge("a", "b")],
        )
        engine = WorkflowEngine()
        result = await engine.execute(definition, {"key": "val"})
        assert result["status"] == "success"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["node_id"] == "a"
        assert result["steps"][1]["node_id"] == "b"

    @pytest.mark.asyncio
    async def test_parallel_execution(self) -> None:
        """Nodes b and c should execute in the same layer (concurrently)."""
        definition = WorkflowDefinition(
            nodes=[_node("a"), _node("b"), _node("c"), _node("d")],
            edges=[
                _edge("a", "b"), _edge("a", "c"),
                _edge("b", "d"), _edge("c", "d"),
            ],
        )
        engine = WorkflowEngine()
        execution_order: list[str] = []

        async def tracking_executor(node, inputs):
            execution_order.append(node.node_id)
            return {"executed": node.node_id}

        result = await engine.execute(
            definition, {}, node_executor=tracking_executor,
        )
        assert result["status"] == "success"
        # a must come first, d must come last
        assert execution_order[0] == "a"
        assert execution_order[-1] == "d"
        # b and c are in the middle (order may vary due to gather)
        assert set(execution_order[1:3]) == {"b", "c"}

    @pytest.mark.asyncio
    async def test_condition_branch_skips_node(self) -> None:
        definition = WorkflowDefinition(
            nodes=[_node("start"), _node("guarded")],
            edges=[_edge("start", "guarded", condition="start.go == yes")],
        )
        engine = WorkflowEngine()

        async def executor(node, inputs):
            return {"go": "no"}

        result = await engine.execute(
            definition, {}, node_executor=executor,
        )
        assert result["status"] == "success"
        # Only start should have executed; guarded was skipped
        executed_ids = [s["node_id"] for s in result["steps"]]
        assert "start" in executed_ids
        assert "guarded" not in executed_ids

    @pytest.mark.asyncio
    async def test_condition_branch_executes_node(self) -> None:
        definition = WorkflowDefinition(
            nodes=[_node("start"), _node("guarded")],
            edges=[_edge("start", "guarded", condition="start.go == yes")],
        )
        engine = WorkflowEngine()

        async def executor(node, inputs):
            return {"go": "yes"}

        result = await engine.execute(
            definition, {}, node_executor=executor,
        )
        executed_ids = [s["node_id"] for s in result["steps"]]
        assert "guarded" in executed_ids

    @pytest.mark.asyncio
    async def test_error_handling_partial_failure(self) -> None:
        definition = WorkflowDefinition(
            nodes=[_node("ok_node"), _node("bad_node")],
            edges=[],  # both are roots, will execute in parallel
        )
        engine = WorkflowEngine()

        async def executor(node, inputs):
            if node.node_id == "bad_node":
                raise ValueError("something broke")
            return {"ok": True}

        result = await engine.execute(
            definition, {}, node_executor=executor,
        )
        assert result["status"] == "partial_failure"
        statuses = {s["node_id"]: s["status"] for s in result["steps"]}
        assert statuses["ok_node"] == "success"
        assert statuses["bad_node"] == "failed"

    @pytest.mark.asyncio
    async def test_empty_workflow(self) -> None:
        definition = WorkflowDefinition(nodes=[], edges=[])
        engine = WorkflowEngine()
        result = await engine.execute(definition, {})
        assert result["status"] == "success"
        assert result["steps"] == []

    @pytest.mark.asyncio
    async def test_input_mappings_resolved(self) -> None:
        definition = WorkflowDefinition(
            nodes=[
                _node("producer"),
                _node("consumer", input_mappings={"data": "producer.value"}),
            ],
            edges=[_edge("producer", "consumer")],
        )
        engine = WorkflowEngine()

        async def executor(node, inputs):
            if node.node_id == "producer":
                return {"value": 42}
            return {"received": inputs.get("data")}

        result = await engine.execute(
            definition, {}, node_executor=executor,
        )
        consumer_step = next(
            s for s in result["steps"] if s["node_id"] == "consumer"
        )
        assert consumer_step["result"]["received"] == 42

    @pytest.mark.asyncio
    async def test_wait_node(self) -> None:
        definition = WorkflowDefinition(
            nodes=[_node("w", ntype="wait", input_mappings={"seconds": 0})],
            edges=[],
        )
        engine = WorkflowEngine()
        result = await engine.execute(definition, {})
        assert result["status"] == "success"
        assert result["steps"][0]["result"]["waited"] == 0
