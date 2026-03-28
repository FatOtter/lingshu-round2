"""Integration tests for Sub-Agent tool loading, schema generation, and execution.

T18: Tests that SubAgentManager correctly loads sub-agents as tools,
generates proper tool schemas, handles execution via mocks, and
reports errors when model configuration is missing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.agent.state import CopilotState, SessionContext
from lingshu.copilot.infra.subagents import SubAgentManager, load_as_tool


@pytest.fixture
def mock_subagent() -> MagicMock:
    """Create a mock SubAgent ORM object."""
    agent = MagicMock()
    agent.rid = "ri.subagent.test1"
    agent.api_name = "data_analyst"
    agent.display_name = "Data Analyst"
    agent.description = "Analyzes data and produces reports"
    agent.model_rid = "ri.model.gemini1"
    agent.system_prompt = "You are a data analyst. Analyze data carefully."
    agent.tool_bindings = [
        {"tool": "query_data", "params": {"source": "main"}},
        {"tool": "chart_builder"},
    ]
    agent.safety_policy = {"max_iterations": 10, "allow_write": False}
    agent.enabled = True
    agent.tenant_id = "t1"
    return agent


@pytest.fixture
def mock_subagent_no_model() -> MagicMock:
    """Create a mock SubAgent without model configuration."""
    agent = MagicMock()
    agent.rid = "ri.subagent.test2"
    agent.api_name = "simple_helper"
    agent.display_name = "Simple Helper"
    agent.description = "A helper without a model"
    agent.model_rid = None
    agent.system_prompt = None
    agent.tool_bindings = []
    agent.safety_policy = {}
    agent.enabled = True
    agent.tenant_id = "t1"
    return agent


@pytest.fixture
def mock_subagent_disabled() -> MagicMock:
    """Create a disabled mock SubAgent."""
    agent = MagicMock()
    agent.rid = "ri.subagent.test3"
    agent.api_name = "disabled_agent"
    agent.display_name = "Disabled Agent"
    agent.description = "This agent is disabled"
    agent.model_rid = "ri.model.gemini1"
    agent.system_prompt = "Disabled prompt"
    agent.tool_bindings = []
    agent.safety_policy = {}
    agent.enabled = False
    agent.tenant_id = "t1"
    return agent


class TestSubAgentToolLoading:
    """Test that SubAgentManager loads sub-agents as tools for the main agent."""

    @pytest.mark.asyncio
    async def test_loads_enabled_subagents_as_tools(
        self,
        mock_subagent: MagicMock,
        mock_subagent_disabled: MagicMock,
    ) -> None:
        """Only enabled sub-agents should be loaded as tools."""
        graph = AgentGraph()
        mock_session = AsyncMock()

        with patch.object(
            graph._subagent_manager,
            "query",
            return_value=([mock_subagent, mock_subagent_disabled], 2),
        ):
            tools = await graph.get_subagent_tools(mock_session)

        assert len(tools) == 1
        assert tools[0]["name"] == "subagent_data_analyst"

    @pytest.mark.asyncio
    async def test_loads_empty_when_no_subagents(self) -> None:
        """Should return empty list when no sub-agents exist."""
        graph = AgentGraph()
        mock_session = AsyncMock()

        with patch.object(
            graph._subagent_manager,
            "query",
            return_value=([], 0),
        ):
            tools = await graph.get_subagent_tools(mock_session)

        assert tools == []

    @pytest.mark.asyncio
    async def test_loads_multiple_enabled_subagents(
        self,
        mock_subagent: MagicMock,
        mock_subagent_no_model: MagicMock,
    ) -> None:
        """All enabled sub-agents should be loaded as tools."""
        graph = AgentGraph()
        mock_session = AsyncMock()

        with patch.object(
            graph._subagent_manager,
            "query",
            return_value=([mock_subagent, mock_subagent_no_model], 2),
        ):
            tools = await graph.get_subagent_tools(mock_session)

        assert len(tools) == 2
        tool_names = {t["name"] for t in tools}
        assert "subagent_data_analyst" in tool_names
        assert "subagent_simple_helper" in tool_names


class TestToolSchemaGeneration:
    """Test tool schema generation for sub-agents."""

    def test_schema_has_correct_name(self, mock_subagent: MagicMock) -> None:
        tool = load_as_tool(mock_subagent)
        assert tool["name"] == "subagent_data_analyst"

    def test_schema_has_description(self, mock_subagent: MagicMock) -> None:
        tool = load_as_tool(mock_subagent)
        assert tool["description"] == "Analyzes data and produces reports"

    def test_schema_fallback_description(
        self, mock_subagent_no_model: MagicMock,
    ) -> None:
        """When description is None, falls back to display_name."""
        mock_subagent_no_model.description = None
        tool = load_as_tool(mock_subagent_no_model)
        assert "Simple Helper" in tool["description"]

    def test_schema_has_input_parameter(self, mock_subagent: MagicMock) -> None:
        tool = load_as_tool(mock_subagent)
        props = tool["parameters"]["properties"]
        assert "input" in props
        assert props["input"]["type"] == "string"
        assert "input" in tool["parameters"]["required"]

    def test_schema_metadata_contains_subagent_info(
        self, mock_subagent: MagicMock,
    ) -> None:
        tool = load_as_tool(mock_subagent)
        meta = tool["metadata"]
        assert meta["type"] == "subagent"
        assert meta["rid"] == "ri.subagent.test1"
        assert meta["model_rid"] == "ri.model.gemini1"
        assert meta["system_prompt"] == "You are a data analyst. Analyze data carefully."
        assert len(meta["tool_bindings"]) == 2
        assert meta["safety_policy"]["max_iterations"] == 10

    def test_schema_metadata_handles_missing_model(
        self, mock_subagent_no_model: MagicMock,
    ) -> None:
        tool = load_as_tool(mock_subagent_no_model)
        meta = tool["metadata"]
        assert meta["model_rid"] is None
        assert meta["system_prompt"] is None
        assert meta["tool_bindings"] == []


class TestSubAgentToolExecution:
    """Test sub-agent tool execution via mock."""

    @pytest.mark.asyncio
    async def test_execute_subagent_returns_events(self) -> None:
        """Executing a sub-agent tool should return tool_start, text_delta, tool_end events."""
        graph = AgentGraph()
        mock_session = AsyncMock()

        subagent_tool = {
            "name": "subagent_data_analyst",
            "description": "Analyzes data",
            "metadata": {
                "type": "subagent",
                "rid": "ri.subagent.test1",
                "system_prompt": "You are a data analyst.",
                "tool_bindings": [{"tool": "query_data"}],
            },
        }

        events = await graph.execute_subagent(
            subagent_tool, "Analyze sales data for Q1", mock_session,
        )

        assert len(events) == 3
        assert events[0]["type"] == "tool_start"
        assert events[0]["tool_name"] == "subagent_data_analyst"
        assert events[1]["type"] == "text_delta"
        assert "Analyze sales data for Q1" in events[1]["content"]
        assert events[2]["type"] == "tool_end"
        assert events[2]["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_subagent_includes_tool_name_in_response(self) -> None:
        """The text_delta should mention the sub-agent name."""
        graph = AgentGraph()
        mock_session = AsyncMock()

        subagent_tool = {
            "name": "subagent_researcher",
            "description": "Research agent",
            "metadata": {
                "type": "subagent",
                "rid": "ri.subagent.r1",
                "system_prompt": "Research prompt",
                "tool_bindings": [],
            },
        }

        events = await graph.execute_subagent(
            subagent_tool, "Look up XYZ", mock_session,
        )

        text_event = events[1]
        assert "subagent_researcher" in text_event["content"]

    @pytest.mark.asyncio
    async def test_process_message_integrates_subagent_tools(self) -> None:
        """process_message in agent mode should include sub-agent tools."""
        graph = AgentGraph()
        mock_session = AsyncMock()

        mock_agent = MagicMock()
        mock_agent.enabled = True
        mock_agent.api_name = "analyst"
        mock_agent.display_name = "Analyst"
        mock_agent.description = "Analysis agent"
        mock_agent.rid = "ri.subagent.a1"
        mock_agent.model_rid = "ri.model.m1"
        mock_agent.system_prompt = "Analyze"
        mock_agent.tool_bindings = []
        mock_agent.safety_policy = {}

        with patch.object(
            graph._subagent_manager,
            "query",
            return_value=([mock_agent], 1),
        ):
            state = CopilotState(
                messages=[],
                context=SessionContext(mode="agent"),
            )
            events = await graph.process_message(
                state, "test integration", mock_session,
            )

        text_events = [e for e in events if e.get("type") == "text_delta"]
        assert len(text_events) >= 1
        assert any("subagent_analyst" in e["content"] for e in text_events)


class TestSubAgentErrorHandling:
    """Test error handling when sub-agent model is not configured."""

    def test_tool_schema_with_no_model_rid(
        self, mock_subagent_no_model: MagicMock,
    ) -> None:
        """Sub-agent without model_rid should still generate a valid tool schema."""
        tool = load_as_tool(mock_subagent_no_model)
        assert tool["metadata"]["model_rid"] is None
        # The tool schema should still be valid
        assert tool["name"] == "subagent_simple_helper"
        assert "input" in tool["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_execute_subagent_without_model_still_works(self) -> None:
        """Even without a model_rid, execute_subagent should return events (stub mode)."""
        graph = AgentGraph()
        mock_session = AsyncMock()

        subagent_tool = {
            "name": "subagent_simple_helper",
            "description": "Helper without model",
            "metadata": {
                "type": "subagent",
                "rid": "ri.subagent.test2",
                "system_prompt": None,
                "tool_bindings": [],
            },
        }

        events = await graph.execute_subagent(
            subagent_tool, "Help me with this", mock_session,
        )

        # Should still return the 3 event structure even without a model
        assert len(events) == 3
        assert events[0]["type"] == "tool_start"
        assert events[2]["type"] == "tool_end"
