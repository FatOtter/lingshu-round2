"""A2UI Protocol: SSE event type definitions."""

import json
from typing import Any

# Event types
EVENT_TEXT_DELTA = "text_delta"
EVENT_COMPONENT = "component"
EVENT_TOOL_START = "tool_start"
EVENT_TOOL_END = "tool_end"
EVENT_THINKING = "thinking"
EVENT_INTERRUPT = "interrupt"
EVENT_ERROR = "error"
EVENT_DONE = "done"

ALL_EVENT_TYPES = frozenset({
    EVENT_TEXT_DELTA, EVENT_COMPONENT, EVENT_TOOL_START, EVENT_TOOL_END,
    EVENT_THINKING, EVENT_INTERRUPT, EVENT_ERROR, EVENT_DONE,
})


class A2UIEvent:
    """A single A2UI SSE event."""

    def __init__(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        event_id: int | None = None,
    ) -> None:
        self.event_type = event_type
        self.data = data or {}
        self.event_id = event_id

    def to_sse(self) -> str:
        """Format as SSE event string."""
        lines: list[str] = []
        if self.event_id is not None:
            lines.append(f"id: {self.event_id}")
        lines.append("event: a2ui")
        payload = {"type": self.event_type, **self.data}
        lines.append(f"data: {json.dumps(payload, ensure_ascii=False)}")
        lines.append("")
        return "\n".join(lines) + "\n"


def text_delta(content: str, event_id: int | None = None) -> A2UIEvent:
    """Create a text_delta event."""
    return A2UIEvent(EVENT_TEXT_DELTA, {"content": content}, event_id)


def component(comp: dict[str, Any], event_id: int | None = None) -> A2UIEvent:
    """Create a component event."""
    return A2UIEvent(EVENT_COMPONENT, {"component": comp}, event_id)


def tool_start(
    tool_name: str, params: dict[str, Any], event_id: int | None = None,
) -> A2UIEvent:
    """Create a tool_start event."""
    return A2UIEvent(
        EVENT_TOOL_START,
        {"tool_name": tool_name, "params": params},
        event_id,
    )


def tool_end(
    tool_name: str, status: str, event_id: int | None = None,
) -> A2UIEvent:
    """Create a tool_end event."""
    return A2UIEvent(
        EVENT_TOOL_END,
        {"tool_name": tool_name, "status": status},
        event_id,
    )


def interrupt_event(
    confirmation: dict[str, Any], event_id: int | None = None,
) -> A2UIEvent:
    """Create an interrupt event."""
    return A2UIEvent(EVENT_INTERRUPT, {"confirmation": confirmation}, event_id)


def error_event(message: str, event_id: int | None = None) -> A2UIEvent:
    """Create an error event."""
    return A2UIEvent(EVENT_ERROR, {"message": message}, event_id)


def done_event(event_id: int | None = None) -> A2UIEvent:
    """Create a done event."""
    return A2UIEvent(EVENT_DONE, {}, event_id)
