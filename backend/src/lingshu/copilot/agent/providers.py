"""Multi-model LLM provider abstraction layer.

Supports Gemini, OpenAI, and Anthropic providers via a unified Protocol.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM provider implementations."""

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks from the LLM."""
        ...

    async def chat_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Non-streaming call that may return tool calls.

        Returns:
            {"text": "...", "tool_calls": [{"name": "...", "args": {...}}]}
        """
        ...


class GeminiProvider:
    """Wraps existing GeminiClient to implement LLMProvider."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        from lingshu.copilot.agent.llm import GeminiClient

        self._client = GeminiClient(api_key=api_key, model=model)

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        async for chunk in self._client.chat(system_prompt, messages, tools):
            yield chunk

    async def chat_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._client.chat_with_tools(system_prompt, messages, tools)


class OpenAIProvider:
    """OpenAI-compatible LLM provider using AsyncOpenAI."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAIProvider. "
                "Install with: pip install openai"
            ) from exc

        self._model = model
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

    def _format_messages(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert internal message format to OpenAI format."""
        formatted: list[dict[str, Any]] = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg.get("role", "user")

            # Handle tool results
            tool_results = msg.get("tool_results")
            if tool_results:
                for tr in tool_results:
                    formatted.append({
                        "role": "tool",
                        "tool_call_id": tr.get("call_id", tr["name"]),
                        "content": json.dumps(tr["result"]),
                    })
                continue

            # Handle assistant messages with tool calls
            tool_calls = msg.get("tool_calls")
            if tool_calls and role == "assistant":
                openai_tool_calls = []
                for i, tc in enumerate(tool_calls):
                    openai_tool_calls.append({
                        "id": tc.get("call_id", tc["name"]),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"]),
                        },
                    })
                entry: dict[str, Any] = {
                    "role": "assistant",
                    "tool_calls": openai_tool_calls,
                }
                content = msg.get("content", "")
                if content:
                    entry["content"] = content
                formatted.append(entry)
                continue

            content = msg.get("content", "")
            if content:
                formatted.append({"role": role, "content": content})

        return formatted

    def _format_tools(
        self, tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert internal tool schema to OpenAI function format."""
        openai_tools: list[dict[str, Any]] = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            })
        return openai_tools

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        formatted = self._format_messages(system_prompt, messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": formatted,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception:
            logger.exception("OpenAI streaming error")
            yield "I'm sorry, I encountered an error processing your request."

    async def chat_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        formatted = self._format_messages(system_prompt, messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": formatted,
        }
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception:
            logger.exception("OpenAI tool call error")
            return {
                "text": "I'm sorry, I encountered an error processing your request.",
                "tool_calls": [],
            }

        choice = response.choices[0] if response.choices else None
        text = choice.message.content or "" if choice else ""
        tool_calls: list[dict[str, Any]] = []

        if choice and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append({
                    "name": tc.function.name,
                    "args": args,
                    "call_id": tc.id,
                })

        return {"text": text, "tool_calls": tool_calls}


class AnthropicProvider:
    """Anthropic LLM provider using AsyncAnthropic."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is required for AnthropicProvider. "
                "Install with: pip install anthropic"
            ) from exc

        self._model = model
        self._client = AsyncAnthropic(api_key=api_key)

    def _format_messages(
        self, messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert internal message format to Anthropic format."""
        formatted: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")

            # Handle tool results
            tool_results = msg.get("tool_results")
            if tool_results:
                content_blocks = []
                for tr in tool_results:
                    content_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": tr.get("call_id", tr["name"]),
                        "content": json.dumps(tr["result"]),
                    })
                formatted.append({"role": "user", "content": content_blocks})
                continue

            # Handle assistant messages with tool calls
            tool_calls = msg.get("tool_calls")
            if tool_calls and role == "assistant":
                content_blocks = []
                text = msg.get("content", "")
                if text:
                    content_blocks.append({"type": "text", "text": text})
                for tc in tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("call_id", tc["name"]),
                        "name": tc["name"],
                        "input": tc["args"],
                    })
                formatted.append({"role": "assistant", "content": content_blocks})
                continue

            content = msg.get("content", "")
            if content:
                formatted.append({"role": role, "content": content})

        return formatted

    def _format_tools(
        self, tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert internal tool schema to Anthropic tool format."""
        anthropic_tools: list[dict[str, Any]] = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("parameters", {}),
            })
        return anthropic_tools

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        formatted = self._format_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": formatted,
            "max_tokens": 4096,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception:
            logger.exception("Anthropic streaming error")
            yield "I'm sorry, I encountered an error processing your request."

    async def chat_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        formatted = self._format_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": formatted,
            "max_tokens": 4096,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        try:
            response = await self._client.messages.create(**kwargs)
        except Exception:
            logger.exception("Anthropic tool call error")
            return {
                "text": "I'm sorry, I encountered an error processing your request.",
                "tool_calls": [],
            }

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "args": block.input,
                    "call_id": block.id,
                })

        return {"text": "".join(text_parts), "tool_calls": tool_calls}


_PROVIDER_MAP: dict[str, type] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def create_provider(
    provider_type: str,
    api_key: str,
    model: str,
    **kwargs: Any,
) -> LLMProvider:
    """Factory function to create provider based on type.

    Args:
        provider_type: One of "gemini", "openai", "anthropic"
        api_key: API key for the provider
        model: Model name/identifier
        **kwargs: Additional provider-specific arguments (e.g., base_url for OpenAI)

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider_type is not supported
    """
    provider_cls = _PROVIDER_MAP.get(provider_type.lower())
    if provider_cls is None:
        supported = ", ".join(sorted(_PROVIDER_MAP.keys()))
        raise ValueError(
            f"Unsupported provider type: {provider_type}. "
            f"Supported: {supported}"
        )
    return provider_cls(api_key=api_key, model=model, **kwargs)
