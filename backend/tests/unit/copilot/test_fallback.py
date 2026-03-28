"""Fallback behavior unit tests.

Tests that the agent's fallback response (when no LLM is configured)
provides helpful guidance, lists providers, and shows tool counts.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.agent.state import CopilotState, SessionContext


class TestFallbackGuidance:
    async def test_fallback_contains_guidance(self) -> None:
        """Fallback message mentions Setting and Models for configuration."""
        graph = AgentGraph(gemini_api_key="")

        state = CopilotState(
            messages=[],
            context=SessionContext(mode="agent"),
        )
        events = await graph.process_message(state, "Hello, help me")

        text = events[0]["content"]
        assert "Setting" in text
        assert "Models" in text

    async def test_fallback_lists_providers(self) -> None:
        """Fallback message includes supported providers."""
        graph = AgentGraph(gemini_api_key="")

        state = CopilotState(
            messages=[],
            context=SessionContext(mode="agent"),
        )
        events = await graph.process_message(state, "What providers are supported?")

        text = events[0]["content"]
        assert "Gemini" in text
        assert "OpenAI" in text
        assert "Anthropic" in text

    async def test_fallback_shows_capabilities(self) -> None:
        """Fallback shows available tool count when tools are present."""
        graph = AgentGraph(gemini_api_key="")
        mock_session = AsyncMock()

        # Mock function service returning capabilities
        mock_func_svc = AsyncMock()
        mock_func_svc.list_capabilities = AsyncMock(return_value=[
            MagicMock(
                type="function", rid="ri.func.1", api_name="calc",
                display_name="Calc", description="Calculate",
                parameters=[], outputs=[], safety_level="SAFETY_READ_ONLY",
                side_effects=[],
            ),
            MagicMock(
                type="function", rid="ri.func.2", api_name="query",
                display_name="Query", description="Query data",
                parameters=[], outputs=[], safety_level="SAFETY_READ_ONLY",
                side_effects=[],
            ),
        ])
        graph._function_service = mock_func_svc

        # Mock subagent manager to return empty
        with patch.object(
            graph._subagent_manager, "query", return_value=([], 0),
        ):
            state = CopilotState(
                messages=[],
                context=SessionContext(mode="agent"),
            )
            events = await graph.process_message(state, "List tools", mock_session)

        text = events[0]["content"]
        # The fallback message includes the tool count
        assert "2" in text
        assert "calc" in text
