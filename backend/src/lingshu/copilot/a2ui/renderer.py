"""A2UI renderer: convert Agent stream chunks to SSE events."""

from typing import Any

from lingshu.copilot.a2ui.protocol import (
    A2UIEvent,
    done_event,
    error_event,
    interrupt_event,
    text_delta,
    tool_end,
    tool_start,
)


class A2UIRenderer:
    """Convert LangGraph stream chunks into A2UI SSE events."""

    def __init__(self) -> None:
        self._event_counter = 0

    def _next_id(self) -> int:
        self._event_counter += 1
        return self._event_counter

    def render_text_chunk(self, content: str) -> A2UIEvent:
        """Render an LLM text token as text_delta event."""
        return text_delta(content, self._next_id())

    def render_tool_start(
        self, tool_name: str, params: dict[str, Any],
    ) -> A2UIEvent:
        """Render tool call start event."""
        return tool_start(tool_name, params, self._next_id())

    def render_tool_end(self, tool_name: str, status: str) -> A2UIEvent:
        """Render tool call end event."""
        return tool_end(tool_name, status, self._next_id())

    def render_component(self, comp: dict[str, Any]) -> A2UIEvent:
        """Render a component event."""
        from lingshu.copilot.a2ui.protocol import component
        return component(comp, self._next_id())

    def render_interrupt(self, confirmation: dict[str, Any]) -> A2UIEvent:
        """Render an interrupt event for human-in-the-loop."""
        return interrupt_event(confirmation, self._next_id())

    def render_error(self, message: str) -> A2UIEvent:
        """Render an error event."""
        return error_event(message, self._next_id())

    def render_done(self) -> A2UIEvent:
        """Render the done event."""
        return done_event(self._next_id())
