"""CopilotService Protocol: cross-module contract."""

from typing import Any, Protocol


class CopilotService(Protocol):
    """Protocol for Copilot module exposed to other modules."""

    async def send_message(
        self,
        session_id: str,
        content: str,
    ) -> list[dict[str, Any]]:
        """Send a message to the agent and get response events."""
        ...
