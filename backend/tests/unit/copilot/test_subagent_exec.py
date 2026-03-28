"""Sub-Agent Execution unit tests.

Tests event wrapping, system prompt passing, tool binding filtering,
informational fallback, and empty tool bindings.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.infra.subagents import load_as_tool


@pytest.fixture
def graph() -> AgentGraph:
    return AgentGraph()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


def _subagent_tool(
    name: str = "subagent_analyst",
    system_prompt: str | None = "Analyze data carefully.",
    tool_bindings: list | None = None,
) -> dict:
    return {
        "name": name,
        "description": "Analysis agent",
        "metadata": {
            "type": "subagent",
            "rid": f"ri.subagent.{name}",
            "system_prompt": system_prompt,
            "tool_bindings": tool_bindings or [],
        },
    }


class TestSubAgentExecution:
    async def test_execute_with_llm_wraps_events(
        self, graph: AgentGraph, mock_session: AsyncMock,
    ) -> None:
        """Verify [agent_name] prefix on text events."""
        tool = _subagent_tool(name="subagent_reporter")

        events = await graph.execute_subagent(tool, "Generate report", mock_session)

        assert len(events) == 3
        assert events[0]["type"] == "tool_start"
        assert events[0]["tool_name"] == "subagent_reporter"
        assert events[1]["type"] == "text_delta"
        assert "[Sub-Agent: subagent_reporter]" in events[1]["content"]
        assert events[2]["type"] == "tool_end"

    async def test_execute_with_llm_uses_system_prompt(
        self, graph: AgentGraph, mock_session: AsyncMock,
    ) -> None:
        """Verify sub-agent's system_prompt is referenced in the response."""
        prompt = "You are a specialized researcher."
        tool = _subagent_tool(system_prompt=prompt)

        events = await graph.execute_subagent(tool, "Research topic X", mock_session)

        text = events[1]["content"]
        # When system_prompt is set, the response mentions its length
        assert f"System prompt length: {len(prompt)}" in text

    async def test_execute_filters_tool_bindings(
        self, graph: AgentGraph, mock_session: AsyncMock,
    ) -> None:
        """Only bound tools are passed to sub-agent (reflected in response)."""
        tool = _subagent_tool(
            tool_bindings=[
                {"tool": "query_data"},
                {"tool": "chart_builder"},
            ],
        )

        events = await graph.execute_subagent(tool, "Analyze data", mock_session)

        text = events[1]["content"]
        assert "Tool bindings: 2" in text

    async def test_execute_no_llm_returns_info(
        self, graph: AgentGraph, mock_session: AsyncMock,
    ) -> None:
        """Informational response without LLM — includes guidance."""
        tool = _subagent_tool(system_prompt=None)

        events = await graph.execute_subagent(tool, "Help me", mock_session)

        assert len(events) == 3
        text = events[1]["content"]
        assert "No system prompt configured" in text
        assert "Full nested agent execution requires model provider configuration" in text

    async def test_execute_empty_tool_bindings(
        self, graph: AgentGraph, mock_session: AsyncMock,
    ) -> None:
        """Empty bindings — no tools available, verify response."""
        tool = _subagent_tool(tool_bindings=[])

        events = await graph.execute_subagent(tool, "Do something", mock_session)

        text = events[1]["content"]
        assert "Tool bindings: 0" in text
        assert events[2]["status"] == "success"
