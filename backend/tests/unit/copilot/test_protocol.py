"""Unit tests for A2UI protocol."""

import json

from lingshu.copilot.a2ui.protocol import (
    A2UIEvent,
    done_event,
    error_event,
    text_delta,
    tool_end,
    tool_start,
)


class TestA2UIEvent:
    def test_to_sse_basic(self) -> None:
        event = A2UIEvent("text_delta", {"content": "hello"}, event_id=1)
        sse = event.to_sse()
        assert "id: 1" in sse
        assert "event: a2ui" in sse
        assert '"type": "text_delta"' in sse
        assert '"content": "hello"' in sse

    def test_to_sse_no_id(self) -> None:
        event = A2UIEvent("done")
        sse = event.to_sse()
        assert "id:" not in sse
        assert "event: a2ui" in sse

    def test_to_sse_parseable_json(self) -> None:
        event = A2UIEvent("component", {"component": {"type": "table"}}, event_id=5)
        sse = event.to_sse()
        data_line = next(line for line in sse.split("\n") if line.startswith("data:"))
        payload = json.loads(data_line[6:])
        assert payload["type"] == "component"
        assert payload["component"]["type"] == "table"


class TestEventHelpers:
    def test_text_delta(self) -> None:
        event = text_delta("hello", 1)
        assert event.event_type == "text_delta"
        assert event.data["content"] == "hello"

    def test_tool_start(self) -> None:
        event = tool_start("query_instances", {"type_rid": "ri.obj.1"}, 2)
        assert event.event_type == "tool_start"
        assert event.data["tool_name"] == "query_instances"

    def test_tool_end(self) -> None:
        event = tool_end("query_instances", "success", 3)
        assert event.event_type == "tool_end"
        assert event.data["status"] == "success"

    def test_error_event(self) -> None:
        event = error_event("something went wrong", 4)
        assert event.event_type == "error"
        assert event.data["message"] == "something went wrong"

    def test_done_event(self) -> None:
        event = done_event(5)
        assert event.event_type == "done"
