"""NativeCRUD engine: pure declarative CRUD without code."""

from datetime import UTC, datetime
from typing import Any

from lingshu.function.actions.engines.base import EngineResult
from lingshu.infra.context import get_user_id


class NativeCRUDEngine:
    """Declarative CRUD engine defined via field_mappings JSON."""

    async def execute(
        self,
        config: dict[str, Any],
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> EngineResult:
        """Resolve field_mappings and compute writeback values."""
        outputs = config.get("outputs", [])
        computed: dict[str, Any] = {}

        for output in outputs:
            output_name = output.get("name", "")
            field_mappings = output.get("field_mappings", [])
            resolved_fields = self._resolve_field_mappings(
                field_mappings, resolved_params, instances,
            )
            computed[output_name] = resolved_fields

        return EngineResult(
            data={"outputs": list(computed.keys())},
            computed_values=computed,
        )

    def _resolve_field_mappings(
        self,
        field_mappings: list[dict[str, Any]],
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Resolve each field_mapping entry to a concrete value."""
        result: dict[str, Any] = {}

        for mapping in field_mappings:
            target_field = mapping["target_field"]
            source = mapping.get("source")
            value = mapping.get("value")

            if value is not None:
                result[target_field] = self._resolve_builtin(value)
            elif source is not None:
                result[target_field] = self._resolve_source(
                    source, resolved_params, instances,
                )
            # If neither source nor value, skip

        return result

    def _resolve_builtin(self, value: str) -> Any:
        """Resolve built-in variables like $NOW, $USER."""
        if value == "$NOW":
            return datetime.now(tz=UTC).isoformat()
        if value == "$USER":
            return get_user_id()
        return value

    def _resolve_source(
        self,
        source: str,
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> Any:
        """Resolve parameter expression like 'param_name' or 'param_name.field'."""
        parts = source.split(".", 1)
        param_name = parts[0]

        # Try instance fields first (param_name.field)
        if len(parts) == 2 and param_name in instances:
            field_name = parts[1]
            return instances[param_name].get(field_name)

        # Direct parameter value
        return resolved_params.get(param_name)
