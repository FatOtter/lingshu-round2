"""Virtual expression evaluator: compute virtual fields from physical data."""

import ast
import operator
from typing import Any

# Supported binary operators
_BINARY_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def evaluate_expression(expression: str, row: dict[str, Any]) -> Any:
    """Evaluate a virtual expression against a row of data.

    Supports basic arithmetic (+, -, *, /) and field references.
    Field references are resolved from the row data.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        return _eval_node(tree.body, row)
    except Exception:
        return None


def _eval_node(node: ast.expr, row: dict[str, Any]) -> Any:
    """Recursively evaluate an AST node."""
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        # Field reference
        return row.get(node.id)

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, row)
        right = _eval_node(node.right, row)
        op_func = _BINARY_OPS.get(type(node.op))
        if op_func and left is not None and right is not None:
            return op_func(left, right)
        return None

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        operand = _eval_node(node.operand, row)
        if operand is not None:
            return -operand
        return None

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        func_name = node.func.id.upper()
        args = [_eval_node(arg, row) for arg in node.args]
        return _call_builtin(func_name, args)

    return None


def _call_builtin(func_name: str, args: list[Any]) -> Any:
    """Evaluate built-in functions."""
    if func_name == "CONCAT":
        return "".join(str(a) for a in args if a is not None)
    if func_name == "IF" and len(args) == 3:
        return args[1] if args[0] else args[2]
    if func_name == "ABS" and len(args) == 1 and args[0] is not None:
        return abs(args[0])
    if func_name == "ROUND" and len(args) >= 1 and args[0] is not None:
        ndigits = int(args[1]) if len(args) > 1 and args[1] is not None else 0
        return round(args[0], ndigits)
    return None


def apply_virtual_fields(
    rows: list[dict[str, Any]],
    virtual_fields: dict[str, str],
) -> list[dict[str, Any]]:
    """Apply virtual field expressions to all rows."""
    if not virtual_fields:
        return rows

    result = []
    for row in rows:
        enriched = dict(row)
        for field_name, expression in virtual_fields.items():
            enriched[field_name] = evaluate_expression(expression, enriched)
        result.append(enriched)
    return result
