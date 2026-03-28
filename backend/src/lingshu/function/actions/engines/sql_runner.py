"""SQLRunner engine: SQL template rendering with parameter binding."""

import re
from typing import Any

from lingshu.function.actions.engines.base import EngineResult
from lingshu.infra.errors import AppError, ErrorCode

# Patterns for template resolution
_BRACE_PATTERN = re.compile(r"\{\{(.+?)\}\}")
_BIND_PATTERN = re.compile(r":([a-zA-Z_][a-zA-Z0-9_.]*)")


class SQLRunnerEngine:
    """Execute SQL templates with parameter binding."""

    async def execute(
        self,
        config: dict[str, Any],
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> EngineResult:
        """Render a SQL template and collect bind parameters.

        config keys:
          - template: str — SQL with ``{{...}}`` substitutions and ``:param`` bindings
          - connection_rid: str — target data source (used for routing in P2)
          - outputs: list — optional output descriptors
        """
        template = config.get("template")
        if not template:
            raise AppError(
                code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                message="SQLRunner engine requires a 'template' in config",
            )

        connection_rid = config.get("connection_rid", "")
        outputs = config.get("outputs", [])

        # Step 1: resolve {{...}} placeholders (table names, asset paths)
        rendered = _resolve_braces(template, resolved_params, instances)

        # Step 2: collect :param bind parameters
        bind_params = _collect_bind_params(rendered, resolved_params, instances)

        result_data = {
            "rendered_sql": rendered,
            "bind_params": bind_params,
            "connection_rid": connection_rid,
        }

        # Build computed_values from outputs config
        computed: dict[str, Any] = {}
        for output in outputs:
            name = output.get("name", "")
            computed[name] = result_data

        return EngineResult(data=result_data, computed_values=computed)


def _resolve_braces(
    template: str,
    resolved_params: dict[str, Any],
    instances: dict[str, dict[str, Any]],
) -> str:
    """Replace ``{{param_name.field}}`` with actual values."""

    def _replacer(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        value = _lookup(expr, resolved_params, instances)
        if value is None:
            return match.group(0)  # leave unresolved
        return str(value)

    return _BRACE_PATTERN.sub(_replacer, template)


def _collect_bind_params(
    rendered: str,
    resolved_params: dict[str, Any],
    instances: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Extract ``:param_name`` and ``:param_name.field`` references."""
    params: dict[str, Any] = {}

    for match in _BIND_PATTERN.finditer(rendered):
        expr = match.group(1)
        if expr in params:
            continue
        value = _lookup(expr, resolved_params, instances)
        params[expr] = value

    return params


def _lookup(
    expr: str,
    resolved_params: dict[str, Any],
    instances: dict[str, dict[str, Any]],
) -> Any:
    """Resolve a dotted expression against params and instances."""
    parts = expr.split(".", 1)
    param_name = parts[0]

    if len(parts) == 2:
        field_name = parts[1]
        # Instance fields first
        if param_name in instances:
            return instances[param_name].get(field_name)
        # Nested resolved param
        param_val = resolved_params.get(param_name)
        if isinstance(param_val, dict):
            return param_val.get(field_name)
        return None

    return resolved_params.get(param_name)
