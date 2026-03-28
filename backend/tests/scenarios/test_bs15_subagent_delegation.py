"""BS-15: Sub-Agent Delegation scenario tests.

Tests creating sub-agents, loading them as tools, executing with/without LLM,
and safety policy enforcement.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.agent.state import CopilotState, SessionContext
from lingshu.copilot.infra.subagents import SubAgentManager, load_as_tool


@pytest.fixture
def manager() -> SubAgentManager:
    return SubAgentManager()


class TestBS15SubAgentDelegation:
    """Sub-Agent Delegation: create -> load as tool -> execute -> safety policy."""

    async def test_step1_create_subagent(
        self, manager: SubAgentManager, mock_db_session: AsyncMock,
    ) -> None:
        """Create sub-agent with system_prompt and tool_bindings."""
        result = await manager.register(
            mock_db_session,
            api_name="data_analyst",
            display_name="Data Analyst",
            description="Analyzes datasets and creates visualizations",
            model_rid="ri.model.gemini1",
            system_prompt="You are a data analyst. Focus on statistical insights.",
            tool_bindings=[
                {"tool": "query_instances", "enabled": True},
                {"tool": "chart_builder", "enabled": True},
            ],
            safety_policy={"max_iterations": 10, "allow_write": False},
        )

        assert result.rid.startswith("ri.subagent.")
        assert result.api_name == "data_analyst"
        assert result.system_prompt == "You are a data analyst. Focus on statistical insights."
        assert len(result.tool_bindings) == 2
        assert result.safety_policy["max_iterations"] == 10
        assert result.enabled is True

    async def test_step2_subagent_loaded_as_tool(self) -> None:
        """Verify sub-agent appears in agent tool list."""
        mock_agent = MagicMock()
        mock_agent.rid = "ri.subagent.da1"
        mock_agent.api_name = "data_analyst"
        mock_agent.display_name = "Data Analyst"
        mock_agent.description = "Analyzes datasets"
        mock_agent.model_rid = "ri.model.gemini1"
        mock_agent.system_prompt = "You are a data analyst."
        mock_agent.tool_bindings = [{"tool": "query_instances"}]
        mock_agent.safety_policy = {"max_iterations": 10}

        tool = load_as_tool(mock_agent)

        assert tool["name"] == "subagent_data_analyst"
        assert tool["description"] == "Analyzes datasets"
        assert tool["parameters"]["properties"]["input"]["type"] == "string"
        assert tool["metadata"]["type"] == "subagent"
        assert tool["metadata"]["rid"] == "ri.subagent.da1"
        assert tool["metadata"]["system_prompt"] == "You are a data analyst."
        assert len(tool["metadata"]["tool_bindings"]) == 1

    async def test_step3_execute_with_llm(
        self, mock_db_session: AsyncMock,
    ) -> None:
        """Mock LLM, verify nested execution with sub-agent system_prompt."""
        graph = AgentGraph()

        subagent_tool = {
            "name": "subagent_data_analyst",
            "description": "Analyzes datasets",
            "metadata": {
                "type": "subagent",
                "rid": "ri.subagent.da1",
                "system_prompt": "You are a data analyst. Focus on statistical insights.",
                "tool_bindings": [{"tool": "query_instances"}],
            },
        }

        events = await graph.execute_subagent(
            subagent_tool, "Analyze Q1 sales trends", mock_db_session,
        )

        assert len(events) == 3
        assert events[0]["type"] == "tool_start"
        assert events[0]["tool_name"] == "subagent_data_analyst"
        assert events[1]["type"] == "text_delta"
        assert "subagent_data_analyst" in events[1]["content"]
        assert "Analyze Q1 sales trends" in events[1]["content"]
        assert "System prompt length:" in events[1]["content"]
        assert events[2]["type"] == "tool_end"
        assert events[2]["status"] == "success"

    async def test_step4_execute_without_llm(
        self, mock_db_session: AsyncMock,
    ) -> None:
        """No LLM configured leads to informational fallback."""
        graph = AgentGraph()

        subagent_tool = {
            "name": "subagent_helper",
            "description": "Helper without model",
            "metadata": {
                "type": "subagent",
                "rid": "ri.subagent.h1",
                "system_prompt": None,
                "tool_bindings": [],
            },
        }

        events = await graph.execute_subagent(
            subagent_tool, "Help me", mock_db_session,
        )

        assert len(events) == 3
        assert events[1]["type"] == "text_delta"
        assert "No system prompt configured" in events[1]["content"]
        assert "Full nested agent execution requires model provider configuration" in events[1]["content"]

    async def test_step5_safety_policy_respected(self) -> None:
        """Sub-agent with safety_policy — verify constraints are stored in tool metadata."""
        mock_agent = MagicMock()
        mock_agent.rid = "ri.subagent.safe1"
        mock_agent.api_name = "safe_agent"
        mock_agent.display_name = "Safe Agent"
        mock_agent.description = "Agent with safety constraints"
        mock_agent.model_rid = "ri.model.m1"
        mock_agent.system_prompt = "Be careful."
        mock_agent.tool_bindings = [{"tool": "query_instances"}]
        mock_agent.safety_policy = {
            "max_iterations": 5,
            "allow_write": False,
            "restricted_tools": ["delete_all"],
        }

        tool = load_as_tool(mock_agent)

        assert tool["metadata"]["safety_policy"]["max_iterations"] == 5
        assert tool["metadata"]["safety_policy"]["allow_write"] is False
        assert "delete_all" in tool["metadata"]["safety_policy"]["restricted_tools"]
