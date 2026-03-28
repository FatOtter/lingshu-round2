"""FunctionService Protocol: cross-module contract."""

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class FunctionService(Protocol):
    """Protocol for Function module exposed to other modules."""

    async def list_capabilities(
        self,
        session: AsyncSession,
        *,
        capability_type: str | None = None,
    ) -> list[Any]:
        """Return unified capability list for Copilot discovery."""
        ...

    async def execute_action(
        self,
        action_type_rid: str,
        params: dict[str, Any],
        *,
        branch: str | None = None,
        skip_confirmation: bool = False,
    ) -> dict[str, Any]:
        """Execute an Ontology Action."""
        ...

    async def execute_function(
        self,
        function_rid: str,
        params: dict[str, Any],
        *,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Execute a Global Function."""
        ...

    async def confirm_execution(
        self,
        execution_id: str,
        session: AsyncSession,
    ) -> Any:
        """Confirm a pending execution."""
        ...

    async def cancel_execution(
        self,
        execution_id: str,
        session: AsyncSession,
    ) -> Any:
        """Cancel a pending execution."""
        ...
