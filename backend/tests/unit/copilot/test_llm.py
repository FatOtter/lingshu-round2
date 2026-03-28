"""Tests for the Gemini LLM client wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.agent.llm import (
    GeminiClient,
    convert_messages_to_gemini,
    convert_tool_schema_to_gemini,
    convert_tools_to_gemini,
)


# ── Tool Schema Conversion ───────────────────────────────────────


def _sample_tool_schema() -> dict:
    return {
        "name": "query_data",
        "description": "Query data from the system",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results"},
                "include_meta": {"type": "boolean", "description": "Include metadata"},
            },
            "required": ["query"],
        },
        "metadata": {"type": "function", "rid": "rid:abc", "safety_level": "SAFETY_READ_ONLY"},
    }


class TestConvertToolSchemaToGemini:
    def test_basic_conversion(self):
        tool = _sample_tool_schema()
        decl = convert_tool_schema_to_gemini(tool)

        assert decl.name == "query_data"
        assert decl.description == "Query data from the system"

    def test_parameter_types_mapped(self):
        tool = _sample_tool_schema()
        decl = convert_tool_schema_to_gemini(tool)
        params = decl.parameters

        assert params.properties["query"].type.value == "STRING"
        assert params.properties["limit"].type.value == "INTEGER"
        assert params.properties["include_meta"].type.value == "BOOLEAN"

    def test_required_fields_preserved(self):
        tool = _sample_tool_schema()
        decl = convert_tool_schema_to_gemini(tool)

        assert decl.parameters.required == ["query"]

    def test_empty_parameters(self):
        tool = {
            "name": "ping",
            "description": "Ping the system",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }
        decl = convert_tool_schema_to_gemini(tool)

        assert decl.name == "ping"
        assert decl.parameters.properties == {}
        # No required field when list is empty
        assert not decl.parameters.required

    def test_number_type_mapped(self):
        tool = {
            "name": "calc",
            "description": "Calculate",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {"type": "number", "description": "A number"},
                },
                "required": [],
            },
        }
        decl = convert_tool_schema_to_gemini(tool)

        assert decl.parameters.properties["value"].type.value == "NUMBER"


class TestConvertToolsToGemini:
    def test_empty_list_returns_none(self):
        result = convert_tools_to_gemini([])
        assert result is None

    def test_multiple_tools(self):
        tools = [
            _sample_tool_schema(),
            {
                "name": "another_tool",
                "description": "Another tool",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        ]
        result = convert_tools_to_gemini(tools)

        assert result is not None
        assert len(result.function_declarations) == 2


# ── Message Conversion ────────────────────────────────────────────


class TestConvertMessagesToGemini:
    def test_user_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = convert_messages_to_gemini(messages)

        assert len(result) == 1
        assert result[0].role == "user"

    def test_assistant_message(self):
        messages = [{"role": "assistant", "content": "Hi there"}]
        result = convert_messages_to_gemini(messages)

        assert len(result) == 1
        assert result[0].role == "model"

    def test_multi_turn_conversation(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"},
        ]
        result = convert_messages_to_gemini(messages)

        assert len(result) == 3
        assert result[0].role == "user"
        assert result[1].role == "model"
        assert result[2].role == "user"

    def test_empty_content_skipped(self):
        messages = [{"role": "user", "content": ""}]
        result = convert_messages_to_gemini(messages)

        assert len(result) == 0

    def test_tool_results_message(self):
        messages = [
            {
                "role": "user",
                "tool_results": [
                    {"name": "query_data", "result": {"data": [1, 2, 3]}},
                ],
            },
        ]
        result = convert_messages_to_gemini(messages)

        assert len(result) == 1
        assert result[0].role == "user"

    def test_assistant_with_tool_calls(self):
        messages = [
            {
                "role": "assistant",
                "content": "Let me look that up.",
                "tool_calls": [
                    {"name": "query_data", "args": {"query": "test"}},
                ],
            },
        ]
        result = convert_messages_to_gemini(messages)

        assert len(result) == 1
        assert result[0].role == "model"
        # Should have both text and function_call parts
        assert len(result[0].parts) == 2


# ── GeminiClient ──────────────────────────────────────────────────


class TestGeminiClientInit:
    @patch("lingshu.copilot.agent.llm.genai.Client")
    def test_creates_client_with_api_key(self, mock_client_cls):
        client = GeminiClient(api_key="test-key", model="gemini-2.0-flash")

        mock_client_cls.assert_called_once_with(api_key="test-key")
        assert client._model == "gemini-2.0-flash"

    @patch("lingshu.copilot.agent.llm.genai.Client")
    def test_default_model(self, mock_client_cls):
        client = GeminiClient(api_key="test-key")

        assert client._model == "gemini-2.0-flash"


class TestGeminiClientChat:
    @pytest.mark.asyncio
    @patch("lingshu.copilot.agent.llm.genai.Client")
    async def test_streams_text_chunks(self, mock_client_cls):
        # Set up async streaming mock
        chunk1 = MagicMock()
        chunk1.text = "Hello "
        chunk2 = MagicMock()
        chunk2.text = "world!"

        async def mock_stream(*args, **kwargs):
            yield chunk1
            yield chunk2

        mock_client = MagicMock()
        mock_client.aio.models.generate_content_stream = mock_stream
        mock_client_cls.return_value = mock_client

        client = GeminiClient(api_key="test-key")
        chunks = []
        async for chunk in client.chat("system", [{"role": "user", "content": "hi"}]):
            chunks.append(chunk)

        assert chunks == ["Hello ", "world!"]

    @pytest.mark.asyncio
    @patch("lingshu.copilot.agent.llm.genai.Client")
    async def test_handles_streaming_error_gracefully(self, mock_client_cls):
        async def mock_stream(*args, **kwargs):
            raise RuntimeError("API error")
            yield  # noqa: F401 — make it a generator

        mock_client = MagicMock()
        mock_client.aio.models.generate_content_stream = mock_stream
        mock_client_cls.return_value = mock_client

        client = GeminiClient(api_key="test-key")
        chunks = []
        async for chunk in client.chat("system", [{"role": "user", "content": "hi"}]):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert "error" in chunks[0].lower()


class TestGeminiClientChatWithTools:
    @pytest.mark.asyncio
    @patch("lingshu.copilot.agent.llm.genai.Client")
    async def test_returns_text_when_no_tool_calls(self, mock_client_cls):
        # Mock response with text only
        text_part = MagicMock()
        text_part.text = "Here is the answer"
        text_part.function_call = None

        candidate = MagicMock()
        candidate.content.parts = [text_part]

        response = MagicMock()
        response.candidates = [candidate]

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=response)
        mock_client_cls.return_value = mock_client

        client = GeminiClient(api_key="test-key")
        result = await client.chat_with_tools(
            "system",
            [{"role": "user", "content": "hi"}],
            [_sample_tool_schema()],
        )

        assert result["text"] == "Here is the answer"
        assert result["tool_calls"] == []

    @pytest.mark.asyncio
    @patch("lingshu.copilot.agent.llm.genai.Client")
    async def test_returns_tool_calls(self, mock_client_cls):
        # Mock response with function call
        fc = MagicMock()
        fc.name = "query_data"
        fc.args = {"query": "test"}

        fc_part = MagicMock()
        fc_part.text = None
        fc_part.function_call = fc

        candidate = MagicMock()
        candidate.content.parts = [fc_part]

        response = MagicMock()
        response.candidates = [candidate]

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=response)
        mock_client_cls.return_value = mock_client

        client = GeminiClient(api_key="test-key")
        result = await client.chat_with_tools(
            "system",
            [{"role": "user", "content": "find data"}],
            [_sample_tool_schema()],
        )

        assert result["text"] == ""
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "query_data"
        assert result["tool_calls"][0]["args"] == {"query": "test"}

    @pytest.mark.asyncio
    @patch("lingshu.copilot.agent.llm.genai.Client")
    async def test_handles_error_gracefully(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API error"),
        )
        mock_client_cls.return_value = mock_client

        client = GeminiClient(api_key="test-key")
        result = await client.chat_with_tools(
            "system",
            [{"role": "user", "content": "hi"}],
            [_sample_tool_schema()],
        )

        assert "error" in result["text"].lower()
        assert result["tool_calls"] == []


# ── AgentGraph Fallback ───────────────────────────────────────────


class TestAgentGraphFallback:
    @pytest.mark.asyncio
    async def test_placeholder_when_no_api_key(self):
        from lingshu.copilot.agent.graph import AgentGraph
        from lingshu.copilot.agent.state import CopilotState, SessionContext

        graph = AgentGraph(gemini_api_key="")
        state = CopilotState(
            messages=[],
            context=SessionContext(mode="agent"),
        )
        events = await graph.process_message(state, "Hello")

        assert len(events) == 2
        assert events[0]["type"] == "text_delta"
        # Updated: fallback now provides setup guidance
        assert "model provider" in events[0]["content"].lower() or "configure" in events[0]["content"].lower()
        assert events[1]["type"] == "done"

    @pytest.mark.asyncio
    async def test_llm_provider_created_when_api_key_set(self):
        from lingshu.copilot.agent.graph import AgentGraph

        with patch("lingshu.copilot.agent.llm.genai.Client"):
            graph = AgentGraph(gemini_api_key="test-key")
            assert graph._llm is not None
