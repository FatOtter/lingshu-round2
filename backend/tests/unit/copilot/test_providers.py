"""Tests for multi-model LLM provider abstraction layer."""

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.agent.providers import (
    AnthropicProvider,
    GeminiProvider,
    LLMProvider,
    OpenAIProvider,
    create_provider,
)


# ── Factory Tests ─────────────────────────────────────────────


class TestCreateProvider:
    """Tests for the provider factory function."""

    def test_create_gemini_provider(self) -> None:
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.dict(
            "lingshu.copilot.agent.providers._PROVIDER_MAP",
            {"gemini": mock_cls},
        ):
            result = create_provider("gemini", "test-key", "gemini-2.0-flash")
            mock_cls.assert_called_once_with(
                api_key="test-key", model="gemini-2.0-flash",
            )
            assert result is mock_cls.return_value

    def test_create_openai_provider(self) -> None:
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.dict(
            "lingshu.copilot.agent.providers._PROVIDER_MAP",
            {"openai": mock_cls},
        ):
            result = create_provider("openai", "sk-test", "gpt-4o")
            mock_cls.assert_called_once_with(
                api_key="sk-test", model="gpt-4o",
            )
            assert result is mock_cls.return_value

    def test_create_anthropic_provider(self) -> None:
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.dict(
            "lingshu.copilot.agent.providers._PROVIDER_MAP",
            {"anthropic": mock_cls},
        ):
            result = create_provider("anthropic", "sk-ant-test", "claude-sonnet-4-20250514")
            mock_cls.assert_called_once_with(
                api_key="sk-ant-test", model="claude-sonnet-4-20250514",
            )
            assert result is mock_cls.return_value

    def test_case_insensitive(self) -> None:
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.dict(
            "lingshu.copilot.agent.providers._PROVIDER_MAP",
            {"gemini": mock_cls},
        ):
            create_provider("Gemini", "key", "model")
            mock_cls.assert_called_once()

    def test_unsupported_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported provider type"):
            create_provider("unsupported", "key", "model")

    def test_passes_extra_kwargs(self) -> None:
        mock_cls = MagicMock(return_value=MagicMock())
        with patch.dict(
            "lingshu.copilot.agent.providers._PROVIDER_MAP",
            {"openai": mock_cls},
        ):
            create_provider("openai", "key", "model", base_url="http://local")
            mock_cls.assert_called_once_with(
                api_key="key", model="model", base_url="http://local",
            )


# ── OpenAI Message Formatting ─────────────────────────────────


class TestOpenAIFormatting:
    """Tests for OpenAI provider message formatting."""

    def _make_provider(self) -> OpenAIProvider:
        """Create provider with mocked openai import."""
        with patch.dict("sys.modules", {"openai": MagicMock()}):
            with patch("lingshu.copilot.agent.providers.OpenAIProvider.__init__", return_value=None):
                provider = object.__new__(OpenAIProvider)
                provider._model = "gpt-4o"
                provider._client = MagicMock()
                return provider

    def test_format_messages_basic(self) -> None:
        provider = self._make_provider()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = provider._format_messages("You are helpful", messages)

        assert result[0] == {"role": "system", "content": "You are helpful"}
        assert result[1] == {"role": "user", "content": "Hello"}
        assert result[2] == {"role": "assistant", "content": "Hi there"}

    def test_format_messages_with_tool_calls(self) -> None:
        provider = self._make_provider()
        messages = [
            {
                "role": "assistant",
                "content": "Let me look that up",
                "tool_calls": [{"name": "search", "args": {"q": "test"}}],
            },
        ]
        result = provider._format_messages("", messages)
        # No system prompt when empty
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert len(result[0]["tool_calls"]) == 1
        assert result[0]["tool_calls"][0]["function"]["name"] == "search"
        assert json.loads(result[0]["tool_calls"][0]["function"]["arguments"]) == {"q": "test"}

    def test_format_messages_with_tool_results(self) -> None:
        provider = self._make_provider()
        messages = [
            {
                "role": "user",
                "tool_results": [
                    {"name": "search", "call_id": "call_1", "result": {"data": "found"}},
                ],
            },
        ]
        result = provider._format_messages("sys", messages)
        # system + tool result
        assert len(result) == 2
        assert result[1]["role"] == "tool"
        assert result[1]["tool_call_id"] == "call_1"

    def test_format_tools(self) -> None:
        provider = self._make_provider()
        tools = [
            {
                "name": "search",
                "description": "Search for items",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        ]
        result = provider._format_tools(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "search"
        assert result[0]["function"]["parameters"]["type"] == "object"


# ── Anthropic Message Formatting ──────────────────────────────


class TestAnthropicFormatting:
    """Tests for Anthropic provider message formatting."""

    def _make_provider(self) -> AnthropicProvider:
        """Create provider with mocked anthropic import."""
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            with patch("lingshu.copilot.agent.providers.AnthropicProvider.__init__", return_value=None):
                provider = object.__new__(AnthropicProvider)
                provider._model = "claude-sonnet-4-20250514"
                provider._client = MagicMock()
                return provider

    def test_format_messages_basic(self) -> None:
        provider = self._make_provider()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = provider._format_messages(messages)
        assert result == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

    def test_format_messages_with_tool_calls(self) -> None:
        provider = self._make_provider()
        messages = [
            {
                "role": "assistant",
                "content": "Using tool",
                "tool_calls": [
                    {"name": "search", "args": {"q": "test"}, "call_id": "tu_1"},
                ],
            },
        ]
        result = provider._format_messages(messages)
        assert len(result) == 1
        content = result[0]["content"]
        assert len(content) == 2
        assert content[0] == {"type": "text", "text": "Using tool"}
        assert content[1]["type"] == "tool_use"
        assert content[1]["name"] == "search"
        assert content[1]["id"] == "tu_1"

    def test_format_messages_with_tool_results(self) -> None:
        provider = self._make_provider()
        messages = [
            {
                "role": "user",
                "tool_results": [
                    {"name": "search", "call_id": "tu_1", "result": {"ok": True}},
                ],
            },
        ]
        result = provider._format_messages(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        content = result[0]["content"]
        assert content[0]["type"] == "tool_result"
        assert content[0]["tool_use_id"] == "tu_1"

    def test_format_tools(self) -> None:
        provider = self._make_provider()
        tools = [
            {
                "name": "get_data",
                "description": "Fetch data",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                },
            },
        ]
        result = provider._format_tools(tools)
        assert len(result) == 1
        assert result[0]["name"] == "get_data"
        assert result[0]["input_schema"]["type"] == "object"


# ── GeminiProvider Wrapping ───────────────────────────────────


class TestGeminiProvider:
    """Tests for GeminiProvider wrapping existing GeminiClient."""

    def test_wraps_gemini_client(self) -> None:
        with patch("lingshu.copilot.agent.providers.GeminiProvider.__init__", return_value=None):
            provider = object.__new__(GeminiProvider)
            mock_client = MagicMock()
            provider._client = mock_client

            # Verify it has the expected interface methods
            assert hasattr(provider, "chat")
            assert hasattr(provider, "chat_with_tools")

    @pytest.mark.asyncio
    async def test_chat_with_tools_delegates(self) -> None:
        with patch("lingshu.copilot.agent.providers.GeminiProvider.__init__", return_value=None):
            provider = object.__new__(GeminiProvider)
            mock_client = AsyncMock()
            mock_client.chat_with_tools = AsyncMock(return_value={
                "text": "response",
                "tool_calls": [],
            })
            provider._client = mock_client

            result = await provider.chat_with_tools("system", [{"role": "user", "content": "hi"}], [])
            assert result["text"] == "response"
            mock_client.chat_with_tools.assert_called_once()


# ── Sub-Agent Execution with Mock LLM ─────────────────────────


class TestSubAgentExecution:
    """Tests for sub-agent execution with a mock LLM provider."""

    @pytest.mark.asyncio
    async def test_subagent_with_llm_provider(self) -> None:
        """When LLM is available, sub-agent should execute nested LLM call."""
        from lingshu.copilot.agent.graph import AgentGraph

        # Create a mock LLM provider
        mock_llm = AsyncMock(spec=LLMProvider)

        async def mock_chat(system_prompt: str, messages: list, tools: Any = None) -> AsyncGenerator[str, None]:
            yield "Sub-agent response"

        mock_llm.chat = mock_chat
        mock_llm.chat_with_tools = AsyncMock(return_value={
            "text": "Sub-agent analyzed the data.",
            "tool_calls": [],
        })

        graph = AgentGraph(llm_provider=mock_llm)

        subagent_tool = {
            "name": "data_analyzer",
            "metadata": {
                "system_prompt": "You analyze data.",
                "tool_bindings": [],
            },
        }

        events = await graph.execute_subagent(
            subagent_tool, "Analyze sales data", AsyncMock(),
        )

        # Should have tool_start, text_delta(s), tool_end
        event_types = [e["type"] for e in events]
        assert "tool_start" in event_types
        assert "tool_end" in event_types
        assert "text_delta" in event_types

        # Text should be prefixed with agent name
        text_events = [e for e in events if e["type"] == "text_delta"]
        assert any("[data_analyzer]" in e["content"] for e in text_events)

    @pytest.mark.asyncio
    async def test_subagent_without_llm_falls_back(self) -> None:
        """When no LLM, sub-agent should return informational response."""
        from lingshu.copilot.agent.graph import AgentGraph

        graph = AgentGraph()

        subagent_tool = {
            "name": "helper_agent",
            "metadata": {
                "system_prompt": "You help users.",
                "tool_bindings": [{"capability_rid": "ri.func.123"}],
            },
        }

        events = await graph.execute_subagent(
            subagent_tool, "Help me", AsyncMock(),
        )

        text_events = [e for e in events if e["type"] == "text_delta"]
        assert len(text_events) == 1
        assert "requires model provider configuration" in text_events[0]["content"]
        assert "Tool bindings: 1" in text_events[0]["content"]


# ── Fallback Response (F8) ────────────────────────────────────


class TestFallbackResponse:
    """Tests for the improved LLM fallback response."""

    @pytest.mark.asyncio
    async def test_fallback_provides_guidance(self) -> None:
        from lingshu.copilot.agent.graph import AgentGraph
        from lingshu.copilot.agent.state import CopilotState, SessionContext

        graph = AgentGraph()
        state = CopilotState(
            messages=[],
            context=SessionContext(mode="agent"),
        )

        events = await graph.process_message(state, "Hello")
        text_events = [e for e in events if e["type"] == "text_delta"]
        assert len(text_events) >= 1

        content = text_events[0]["content"]
        # Should mention setup steps instead of raw placeholder
        assert "Setting" in content
        assert "LINGSHU_COPILOT" in content
        assert "Gemini" in content or "OpenAI" in content

    @pytest.mark.asyncio
    async def test_fallback_shows_available_tools(self) -> None:
        from lingshu.copilot.agent.graph import AgentGraph
        from lingshu.copilot.agent.state import CopilotState, SessionContext

        graph = AgentGraph()
        state = CopilotState(
            messages=[],
            context=SessionContext(mode="agent"),
        )

        # Manually test _build_fallback_response with tools
        tools = [{"name": f"tool_{i}"} for i in range(3)]
        events = graph._build_fallback_response(
            SessionContext(mode="shell", module="ontology"),
            tools, [], "sys", "test",
        )
        text_events = [e for e in events if e["type"] == "text_delta"]
        content = text_events[0]["content"]
        assert "Available capabilities (3)" in content
        assert "SHELL" in content
        assert "ontology" in content


# ── MCP Protocol Tests ────────────────────────────────────────


class TestMcpProtocol:
    """Tests for MCP JSON-RPC protocol helpers."""

    def test_make_jsonrpc_request(self) -> None:
        from lingshu.copilot.infra.mcp import _make_jsonrpc_request

        req = _make_jsonrpc_request("tools/list", request_id=42)
        assert req["jsonrpc"] == "2.0"
        assert req["id"] == 42
        assert req["method"] == "tools/list"
        assert req["params"] == {}

    def test_parse_transport_stdio(self) -> None:
        from lingshu.copilot.infra.mcp import _parse_transport

        transport_type, conn_info = _parse_transport({
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "some-mcp-server"],
        })
        assert transport_type == "stdio"
        assert conn_info == ["npx", "-y", "some-mcp-server"]

    def test_parse_transport_http(self) -> None:
        from lingshu.copilot.infra.mcp import _parse_transport

        transport_type, conn_info = _parse_transport({
            "type": "sse",
            "url": "https://mcp.example.com/sse",
        })
        assert transport_type == "http"
        assert conn_info == "https://mcp.example.com/sse"

    def test_parse_transport_streamable_http(self) -> None:
        from lingshu.copilot.infra.mcp import _parse_transport

        transport_type, conn_info = _parse_transport({
            "type": "streamable-http",
            "url": "https://mcp.example.com/mcp",
        })
        assert transport_type == "http"

    def test_parse_transport_missing_command(self) -> None:
        from lingshu.copilot.infra.mcp import _parse_transport
        from lingshu.infra.errors import AppError

        with pytest.raises(AppError, match="command"):
            _parse_transport({"type": "stdio"})

    def test_parse_transport_missing_url(self) -> None:
        from lingshu.copilot.infra.mcp import _parse_transport
        from lingshu.infra.errors import AppError

        with pytest.raises(AppError, match="url"):
            _parse_transport({"type": "sse"})

    def test_parse_transport_unsupported(self) -> None:
        from lingshu.copilot.infra.mcp import _parse_transport
        from lingshu.infra.errors import AppError

        with pytest.raises(AppError, match="Unsupported"):
            _parse_transport({"type": "websocket"})
