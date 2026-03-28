"""Unit tests for Agent components."""

import pytest

from lingshu.copilot.agent.context import build_context, get_branch_from_context
from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.agent.prompts import build_system_prompt
from lingshu.copilot.agent.state import CopilotState, SessionContext
from lingshu.copilot.agent.tools import build_tool_schemas, make_tool_schema
from lingshu.function.schemas.responses import CapabilityDescriptor


class TestContextManagement:
    def test_build_shell_context(self) -> None:
        ctx = build_context("shell", {
            "module": "ontology",
            "page": "/ontology/object-types",
            "entity_rid": "ri.obj.1",
            "branch": "dev",
        })
        assert ctx["mode"] == "shell"
        assert ctx["module"] == "ontology"
        assert ctx["branch"] == "dev"

    def test_build_agent_context(self) -> None:
        ctx = build_context("agent", {})
        assert ctx["mode"] == "agent"
        assert ctx["branch"] == "main"

    def test_get_branch_default(self) -> None:
        ctx = SessionContext(mode="agent")
        assert get_branch_from_context(ctx) == "main"

    def test_get_branch_custom(self) -> None:
        ctx = SessionContext(mode="shell", branch="dev")
        assert get_branch_from_context(ctx) == "dev"


class TestSystemPrompts:
    def test_shell_prompt_includes_module(self) -> None:
        ctx = SessionContext(
            mode="shell", module="ontology",
            page="/ontology", branch="main",
        )
        prompt = build_system_prompt(ctx)
        assert "ontology" in prompt.lower() or "Ontology" in prompt

    def test_agent_prompt_includes_branch(self) -> None:
        ctx = SessionContext(mode="agent", branch="dev")
        prompt = build_system_prompt(ctx)
        assert "dev" in prompt

    def test_shell_prompt_with_entity(self) -> None:
        ctx = SessionContext(
            mode="shell", module="data",
            page="/data", entity_rid="ri.obj.123",
            branch="main",
        )
        prompt = build_system_prompt(ctx)
        assert "ri.obj.123" in prompt


class TestToolSchemas:
    def test_make_tool_schema(self) -> None:
        cap = CapabilityDescriptor(
            type="function",
            rid="ri.func.1",
            api_name="query_instances",
            display_name="Query Instances",
            description="Query data instances",
            parameters=[
                {
                    "api_name": "type_rid",
                    "display_name": "Type RID",
                    "data_type": "DT_STRING",
                    "required": True,
                },
            ],
            safety_level="SAFETY_READ_ONLY",
        )
        schema = make_tool_schema(cap)
        assert schema["name"] == "query_instances"
        assert "type_rid" in schema["parameters"]["properties"]
        assert "type_rid" in schema["parameters"]["required"]

    def test_build_tool_schemas(self) -> None:
        caps = [
            CapabilityDescriptor(
                type="function", rid="ri.func.1",
                api_name="func1", display_name="F1",
            ),
            CapabilityDescriptor(
                type="action", rid="ri.action.1",
                api_name="action1", display_name="A1",
            ),
        ]
        schemas = build_tool_schemas(caps)
        assert len(schemas) == 2

    def test_integer_param_type(self) -> None:
        cap = CapabilityDescriptor(
            type="function", rid="ri.func.1",
            api_name="test", display_name="Test",
            parameters=[
                {
                    "api_name": "count",
                    "data_type": "DT_INTEGER",
                    "required": False,
                },
            ],
        )
        schema = make_tool_schema(cap)
        assert schema["parameters"]["properties"]["count"]["type"] == "integer"


class TestAgentGraph:
    @pytest.mark.asyncio
    async def test_process_message_p1_no_function_service(self) -> None:
        graph = AgentGraph()
        state = CopilotState(
            messages=[], context=SessionContext(mode="agent"),
        )
        events = await graph.process_message(state, "hello")
        assert len(events) >= 1
        assert events[0]["type"] == "text_delta"
        # Fallback response guides user to configure a provider
        assert "configure" in events[0]["content"].lower() or "model provider" in events[0]["content"].lower()
        assert "AGENT" in events[0]["content"]

    @pytest.mark.asyncio
    async def test_process_message_shell_mode(self) -> None:
        graph = AgentGraph()
        state = CopilotState(
            messages=[],
            context=SessionContext(mode="shell", module="ontology"),
        )
        events = await graph.process_message(state, "query types")
        assert events[0]["type"] == "text_delta"
        assert "SHELL" in events[0]["content"]
        assert "ontology" in events[0]["content"]

    @pytest.mark.asyncio
    async def test_process_message_with_function_service(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_fn = MagicMock()
        mock_fn.list_capabilities = AsyncMock(return_value=[
            CapabilityDescriptor(
                type="function", rid="ri.func.1",
                api_name="func1", display_name="F1",
            ),
        ])

        graph = AgentGraph(function_service=mock_fn)
        state = CopilotState(
            messages=[], context=SessionContext(mode="agent"),
        )
        db_session = AsyncMock()
        events = await graph.process_message(state, "hello", db_session)
        assert "Available capabilities (1)" in events[0]["content"]
