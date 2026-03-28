"""Unit tests for A2UI renderer."""


from lingshu.copilot.a2ui.renderer import A2UIRenderer


class TestA2UIRenderer:
    def test_render_text_chunk(self) -> None:
        renderer = A2UIRenderer()
        event = renderer.render_text_chunk("hello")
        assert event.event_type == "text_delta"
        assert event.data["content"] == "hello"
        assert event.event_id == 1

    def test_render_tool_start(self) -> None:
        renderer = A2UIRenderer()
        event = renderer.render_tool_start("query", {"rid": "ri.obj.1"})
        assert event.event_type == "tool_start"
        assert event.data["tool_name"] == "query"

    def test_render_tool_end(self) -> None:
        renderer = A2UIRenderer()
        event = renderer.render_tool_end("query", "success")
        assert event.event_type == "tool_end"
        assert event.data["status"] == "success"

    def test_render_component(self) -> None:
        renderer = A2UIRenderer()
        event = renderer.render_component({"type": "table", "rows": []})
        assert event.event_type == "component"

    def test_render_error(self) -> None:
        renderer = A2UIRenderer()
        event = renderer.render_error("oops")
        assert event.event_type == "error"

    def test_render_done(self) -> None:
        renderer = A2UIRenderer()
        event = renderer.render_done()
        assert event.event_type == "done"

    def test_event_id_increments(self) -> None:
        renderer = A2UIRenderer()
        e1 = renderer.render_text_chunk("a")
        e2 = renderer.render_text_chunk("b")
        e3 = renderer.render_done()
        assert e1.event_id == 1
        assert e2.event_id == 2
        assert e3.event_id == 3
