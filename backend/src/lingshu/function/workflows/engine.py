"""Workflow execution engine: topological sort, parallel fan-out, condition branching."""

import asyncio
import logging
import operator
from collections import defaultdict
from typing import Any

from lingshu.function.workflows.models import (
    WorkflowDefinition,
    WorkflowEdgeSchema,
    WorkflowNodeSchema,
)
from lingshu.infra.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

# Safety level ordering (highest wins)
SAFETY_LEVEL_ORDER: dict[str, int] = {
    "SAFETY_READ_ONLY": 0,
    "SAFETY_IDEMPOTENT_WRITE": 1,
    "SAFETY_NON_IDEMPOTENT": 2,
    "SAFETY_CRITICAL": 3,
}

SAFETY_LEVELS_BY_RANK = {v: k for k, v in SAFETY_LEVEL_ORDER.items()}

# Supported comparison operators for condition expressions
_CONDITION_OPS: dict[str, Any] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def compute_safety_level(
    node_safety_levels: list[str],
) -> str:
    """Return the highest safety level among all nodes."""
    if not node_safety_levels:
        return "SAFETY_READ_ONLY"
    max_rank = max(
        SAFETY_LEVEL_ORDER.get(lvl, 0) for lvl in node_safety_levels
    )
    return SAFETY_LEVELS_BY_RANK.get(max_rank, "SAFETY_READ_ONLY")


def topological_sort(
    nodes: list[WorkflowNodeSchema],
    edges: list[WorkflowEdgeSchema],
) -> list[list[str]]:
    """Return nodes grouped into parallel execution layers (Kahn's algorithm).

    Each inner list contains node_ids that can be executed concurrently.
    Raises AppError if a cycle is detected.
    """
    node_ids = {n.node_id for n in nodes}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        if edge.target_node_id in node_ids:
            in_degree[edge.target_node_id] += 1
        adjacency[edge.source_node_id].append(edge.target_node_id)

    # Seed with nodes that have no incoming edges
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    layers: list[list[str]] = []
    visited_count = 0

    while queue:
        layers.append(sorted(queue))  # deterministic ordering
        next_queue: list[str] = []
        for nid in queue:
            visited_count += 1
            for neighbour in adjacency[nid]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    next_queue.append(neighbour)
        queue = next_queue

    if visited_count != len(node_ids):
        raise AppError(
            code=ErrorCode.COMMON_INVALID_INPUT,
            message="Workflow DAG contains a cycle",
        )
    return layers


def evaluate_condition(
    expression: str,
    context: dict[str, Any],
) -> bool:
    """Evaluate a simple condition expression against a context dict.

    Supported forms:
      - ``"result.field == value"``
      - ``"result.field > 10"``
      - ``"true"`` / ``"false"``
    """
    expr = expression.strip()
    if expr.lower() == "true":
        return True
    if expr.lower() == "false":
        return False

    # Find the operator
    for op_str in sorted(_CONDITION_OPS, key=len, reverse=True):
        if op_str in expr:
            left_raw, right_raw = expr.split(op_str, 1)
            left_val = _resolve_value(left_raw.strip(), context)
            right_val = _resolve_literal(right_raw.strip())
            return bool(_CONDITION_OPS[op_str](left_val, right_val))

    # Fallback: treat as truthy check on a context path
    val = _resolve_value(expr, context)
    return bool(val)


def _resolve_value(path: str, context: dict[str, Any]) -> Any:
    """Resolve a dotted path like ``node_a.data.count`` from context."""
    parts = path.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _resolve_literal(raw: str) -> Any:
    """Parse a literal value from a condition expression."""
    # Boolean
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    # Numeric
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    # String (strip quotes)
    if (raw.startswith("'") and raw.endswith("'")) or (
        raw.startswith('"') and raw.endswith('"')
    ):
        return raw[1:-1]
    return raw


class WorkflowEngine:
    """Execute a workflow DAG with support for parallel fan-out."""

    async def execute(
        self,
        definition: WorkflowDefinition,
        inputs: dict[str, Any],
        *,
        node_executor: Any | None = None,
    ) -> dict[str, Any]:
        """Execute the workflow and return step-by-step results.

        Args:
            definition: Parsed WorkflowDefinition with nodes and edges.
            inputs: Initial input values fed to root nodes.
            node_executor: Optional async callable ``(node, resolved_inputs) -> result``.
                           If None, a stub executor that echoes inputs is used.

        Returns:
            Dict with ``status``, ``steps`` (per-node results), and ``outputs``.
        """
        if not definition.nodes:
            return {"status": "success", "steps": [], "outputs": {}}

        layers = topological_sort(definition.nodes, definition.edges)
        node_map = {n.node_id: n for n in definition.nodes}
        edge_map = self._build_edge_map(definition.edges)

        # Context accumulates outputs keyed by node_id
        context: dict[str, Any] = {"_inputs": inputs}
        steps: list[dict[str, Any]] = []
        overall_status = "success"

        for layer in layers:
            # Filter nodes whose incoming condition edges are satisfied
            executable = []
            for nid in layer:
                if self._should_execute(nid, edge_map, context):
                    executable.append(nid)

            if not executable:
                continue

            # Execute all nodes in the layer concurrently
            tasks = [
                self._execute_node(
                    node_map[nid], context, inputs, node_executor,
                )
                for nid in executable
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for nid, result in zip(executable, results):
                if isinstance(result, Exception):
                    step = {
                        "node_id": nid,
                        "status": "failed",
                        "error": str(result),
                    }
                    overall_status = "partial_failure"
                else:
                    step = {
                        "node_id": nid,
                        "status": "success",
                        "result": result,
                    }
                    context[nid] = result
                steps.append(step)

        return {
            "status": overall_status,
            "steps": steps,
            "outputs": {
                k: v for k, v in context.items() if k != "_inputs"
            },
        }

    # ── Internals ────────────────────────────────────────────────

    @staticmethod
    def _build_edge_map(
        edges: list[WorkflowEdgeSchema],
    ) -> dict[str, list[WorkflowEdgeSchema]]:
        """Map target_node_id -> list of incoming edges."""
        result: dict[str, list[WorkflowEdgeSchema]] = defaultdict(list)
        for edge in edges:
            result[edge.target_node_id].append(edge)
        return result

    @staticmethod
    def _should_execute(
        node_id: str,
        edge_map: dict[str, list[WorkflowEdgeSchema]],
        context: dict[str, Any],
    ) -> bool:
        """Check if all incoming conditional edges are satisfied."""
        incoming = edge_map.get(node_id, [])
        for edge in incoming:
            if edge.condition:
                if not evaluate_condition(edge.condition, context):
                    return False
        return True

    @staticmethod
    async def _execute_node(
        node: WorkflowNodeSchema,
        context: dict[str, Any],
        inputs: dict[str, Any],
        node_executor: Any | None,
    ) -> Any:
        """Execute a single workflow node."""
        # Resolve input mappings from context
        resolved_inputs: dict[str, Any] = {}
        for param_name, source_path in node.input_mappings.items():
            if isinstance(source_path, str):
                resolved_inputs[param_name] = _resolve_value(
                    source_path, {**context, "_inputs": inputs},
                )
            else:
                resolved_inputs[param_name] = source_path

        if node.type == "condition":
            # Condition nodes evaluate their first input mapping as a boolean
            expr = node.input_mappings.get("expression", "true")
            return {"result": evaluate_condition(str(expr), context)}

        if node.type == "wait":
            delay = node.input_mappings.get("seconds", 0)
            await asyncio.sleep(float(delay) if delay else 0)
            return {"waited": delay}

        if node_executor is not None:
            return await node_executor(node, resolved_inputs)

        # Default stub: echo resolved inputs
        return {"node_id": node.node_id, "inputs": resolved_inputs}
