"""Engine Protocol: abstract interface for all execution engines."""

from typing import Any, Protocol


class EngineResult:
    """Result from engine execution."""

    def __init__(
        self,
        data: Any = None,
        computed_values: dict[str, Any] | None = None,
    ) -> None:
        self.data = data
        self.computed_values = computed_values or {}


class Engine(Protocol):
    """Protocol for execution engines."""

    async def execute(
        self,
        config: dict[str, Any],
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> EngineResult:
        """Execute engine logic and return result."""
        ...
