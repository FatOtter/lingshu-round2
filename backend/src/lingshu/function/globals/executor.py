"""Global Function executor: dispatch by implementation type."""

from typing import Any

from lingshu.function.actions.engines.python_venv import PythonVenvEngine
from lingshu.function.actions.engines.webhook import WebhookEngine
from lingshu.function.globals.builtins import BuiltinFunctions
from lingshu.infra.errors import AppError, ErrorCode


class GlobalFunctionExecutor:
    """Execute global functions based on their implementation type."""

    def __init__(self, builtins: BuiltinFunctions) -> None:
        self._builtins = builtins
        self._python_venv = PythonVenvEngine()
        self._webhook = WebhookEngine()

    async def execute(
        self,
        implementation: dict[str, Any],
        params: dict[str, Any],
        tenant_id: str,
    ) -> Any:
        """Execute a global function by dispatching to the right handler."""
        impl_type = implementation.get("type", "")

        if impl_type == "builtin":
            handler = implementation.get("handler", "")
            return await self._builtins.execute(handler, params, tenant_id)

        if impl_type == "python":
            script = implementation.get("script", "")
            config = {
                "script": script,
                "timeout": implementation.get("timeout", 30),
            }
            result = await self._python_venv.execute(
                config, params, instances={},
            )
            return result.data

        if impl_type == "webhook":
            webhook_config = {
                k: v for k, v in implementation.items() if k != "type"
            }
            result = await self._webhook.execute(
                webhook_config, params, instances={},
            )
            return result.data

        raise AppError(
            code=ErrorCode.FUNCTION_EXECUTION_FAILED,
            message=f"Unknown function implementation type: {impl_type}",
        )
