"""Unit tests for SubAgentManager and sub-agent orchestration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.infra.subagents import SubAgentManager, load_as_tool
from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.agent.state import CopilotState, SessionContext
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def manager() -> SubAgentManager:
    return SubAgentManager()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


class TestSubAgentManager:
    @pytest.mark.asyncio
    async def test_register_sub_agent(
        self, manager: SubAgentManager, mock_session: AsyncMock,
    ) -> None:
        with patch(
            "lingshu.copilot.infra.subagents.get_tenant_id",
            return_value="t1",
        ):
            result = await manager.register(
                mock_session,
                api_name="researcher",
                display_name="Researcher",
                description="Searches and analyzes data",
                model_rid="ri.model.abc",
                system_prompt="You are a research assistant.",
                tool_bindings=[{"tool": "search"}],
                safety_policy={"max_iterations": 5},
            )
        assert result.rid.startswith("ri.subagent.")
        assert result.api_name == "researcher"
        assert result.display_name == "Researcher"
        assert result.description == "Searches and analyzes data"
        assert result.model_rid == "ri.model.abc"
        assert result.system_prompt == "You are a research assistant."
        assert result.tool_bindings == [{"tool": "search"}]
        assert result.safety_policy == {"max_iterations": 5}
        assert result.enabled is True
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_sub_agent_defaults(
        self, manager: SubAgentManager, mock_session: AsyncMock,
    ) -> None:
        with patch(
            "lingshu.copilot.infra.subagents.get_tenant_id",
            return_value="t1",
        ):
            result = await manager.register(
                mock_session,
                api_name="basic",
                display_name="Basic Agent",
            )
        assert result.description is None
        assert result.model_rid is None
        assert result.system_prompt is None
        assert result.tool_bindings == []
        assert result.safety_policy == {}
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_get_sub_agent_not_found(
        self, manager: SubAgentManager, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "lingshu.copilot.infra.subagents.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.get("ri.subagent.missing", mock_session)
        assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_sub_agent_not_found(
        self, manager: SubAgentManager, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "lingshu.copilot.infra.subagents.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.delete("ri.subagent.missing", mock_session)
        assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND

    @pytest.mark.asyncio
    async def test_set_enabled(
        self, manager: SubAgentManager, mock_session: AsyncMock,
    ) -> None:
        mock_agent = MagicMock()
        mock_agent.rid = "ri.subagent.abc"
        mock_agent.enabled = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_agent)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "lingshu.copilot.infra.subagents.get_tenant_id",
            return_value="t1",
        ):
            result = await manager.set_enabled(
                "ri.subagent.abc", False, mock_session,
            )
        assert result.rid == "ri.subagent.abc"


class TestLoadAsTool:
    def test_load_as_tool_with_description(self) -> None:
        agent = MagicMock()
        agent.rid = "ri.subagent.abc"
        agent.api_name = "researcher"
        agent.display_name = "Researcher"
        agent.description = "Searches and analyzes data"
        agent.model_rid = "ri.model.xyz"
        agent.system_prompt = "You are a research assistant."
        agent.tool_bindings = [{"tool": "search"}]
        agent.safety_policy = {"max_iterations": 5}

        tool = load_as_tool(agent)
        assert tool["name"] == "subagent_researcher"
        assert tool["description"] == "Searches and analyzes data"
        assert tool["parameters"]["properties"]["input"]["type"] == "string"
        assert "input" in tool["parameters"]["required"]
        assert tool["metadata"]["type"] == "subagent"
        assert tool["metadata"]["rid"] == "ri.subagent.abc"
        assert tool["metadata"]["model_rid"] == "ri.model.xyz"
        assert tool["metadata"]["system_prompt"] == "You are a research assistant."

    def test_load_as_tool_without_description(self) -> None:
        agent = MagicMock()
        agent.rid = "ri.subagent.def"
        agent.api_name = "helper"
        agent.display_name = "Helper Agent"
        agent.description = None
        agent.model_rid = None
        agent.system_prompt = None
        agent.tool_bindings = []
        agent.safety_policy = {}

        tool = load_as_tool(agent)
        assert tool["name"] == "subagent_helper"
        assert tool["description"] == "Delegate to sub-agent: Helper Agent"


class TestMultiAgentOrchestration:
    @pytest.mark.asyncio
    async def test_get_subagent_tools(self) -> None:
        graph = AgentGraph()

        mock_agent_enabled = MagicMock()
        mock_agent_enabled.enabled = True
        mock_agent_enabled.api_name = "researcher"
        mock_agent_enabled.display_name = "Researcher"
        mock_agent_enabled.description = "Research agent"
        mock_agent_enabled.rid = "ri.subagent.1"
        mock_agent_enabled.model_rid = None
        mock_agent_enabled.system_prompt = "Research prompt"
        mock_agent_enabled.tool_bindings = []
        mock_agent_enabled.safety_policy = {}

        mock_agent_disabled = MagicMock()
        mock_agent_disabled.enabled = False

        mock_session = AsyncMock()

        with patch.object(
            graph._subagent_manager,
            "query",
            return_value=([mock_agent_enabled, mock_agent_disabled], 2),
        ):
            tools = await graph.get_subagent_tools(mock_session)

        assert len(tools) == 1
        assert tools[0]["name"] == "subagent_researcher"

    @pytest.mark.asyncio
    async def test_execute_subagent(self) -> None:
        graph = AgentGraph()
        mock_session = AsyncMock()

        subagent_tool = {
            "name": "subagent_researcher",
            "description": "Research agent",
            "metadata": {
                "type": "subagent",
                "rid": "ri.subagent.1",
                "system_prompt": "You are a research assistant.",
                "tool_bindings": [{"tool": "search"}],
            },
        }

        events = await graph.execute_subagent(
            subagent_tool, "Find data about X", mock_session,
        )

        assert len(events) == 3
        assert events[0]["type"] == "tool_start"
        assert events[0]["tool_name"] == "subagent_researcher"
        assert events[1]["type"] == "text_delta"
        assert "Sub-Agent: subagent_researcher" in events[1]["content"]
        assert "Find data about X" in events[1]["content"]
        assert events[2]["type"] == "tool_end"
        assert events[2]["status"] == "success"

    @pytest.mark.asyncio
    async def test_process_message_includes_subagents(self) -> None:
        graph = AgentGraph()
        mock_session = AsyncMock()

        mock_agent = MagicMock()
        mock_agent.enabled = True
        mock_agent.api_name = "helper"
        mock_agent.display_name = "Helper"
        mock_agent.description = "Helper agent"
        mock_agent.rid = "ri.subagent.1"
        mock_agent.model_rid = None
        mock_agent.system_prompt = "Help prompt"
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
                state, "test message", mock_session,
            )

        text_events = [e for e in events if e.get("type") == "text_delta"]
        assert len(text_events) == 1
        # Updated: fallback now shows sub-agents in a structured format
        assert "subagent_helper" in text_events[0]["content"]
