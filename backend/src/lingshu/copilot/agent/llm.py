"""Gemini LLM client wrapper for async streaming and tool calling."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def convert_tool_schema_to_gemini(tool: dict[str, Any]) -> types.FunctionDeclaration:
    """Convert an OpenAI-style tool schema to a Gemini FunctionDeclaration.

    Input format (from tools.py make_tool_schema):
        {
            "name": "...",
            "description": "...",
            "parameters": {
                "type": "object",
                "properties": { ... },
                "required": [ ... ],
            },
            "metadata": { ... },
        }
    """
    params = tool.get("parameters", {})
    properties: dict[str, Any] = {}

    type_map = {
        "string": "STRING",
        "integer": "INTEGER",
        "number": "NUMBER",
        "boolean": "BOOLEAN",
    }

    for prop_name, prop_schema in params.get("properties", {}).items():
        prop_type = type_map.get(prop_schema.get("type", "string"), "STRING")
        prop_def: dict[str, Any] = {"type": prop_type}
        if prop_schema.get("description"):
            prop_def["description"] = prop_schema["description"]
        properties[prop_name] = prop_def

    schema: dict[str, Any] = {
        "type": "OBJECT",
        "properties": properties,
    }
    required = params.get("required", [])
    if required:
        schema["required"] = required

    return types.FunctionDeclaration(
        name=tool["name"],
        description=tool.get("description", ""),
        parameters=schema,
    )


def convert_tools_to_gemini(tools: list[dict[str, Any]]) -> types.Tool | None:
    """Convert a list of tool schemas to a single Gemini Tool object."""
    if not tools:
        return None
    declarations = [convert_tool_schema_to_gemini(t) for t in tools]
    return types.Tool(function_declarations=declarations)


def convert_messages_to_gemini(
    messages: list[dict[str, Any]],
) -> list[types.Content]:
    """Convert conversation messages to Gemini Content format.

    Input: [{"role": "user"|"assistant", "content": "..."}]
    Output: [types.Content(role="user"|"model", parts=[types.Part(...)])]
    """
    contents: list[types.Content] = []
    for msg in messages:
        role = msg.get("role", "user")
        gemini_role = "model" if role == "assistant" else "user"
        content = msg.get("content", "")

        # Handle tool call results in messages
        tool_results = msg.get("tool_results")
        if tool_results:
            parts = []
            for tr in tool_results:
                parts.append(types.Part.from_function_response(
                    name=tr["name"],
                    response=tr["result"],
                ))
            contents.append(types.Content(role="user", parts=parts))
            continue

        # Handle assistant messages with tool calls
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            parts = []
            if content:
                parts.append(types.Part.from_text(text=content))
            for tc in tool_calls:
                parts.append(types.Part.from_function_call(
                    name=tc["name"],
                    args=tc["args"],
                ))
            contents.append(types.Content(role="model", parts=parts))
            continue

        if content:
            contents.append(types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=content)],
            ))
    return contents


class GeminiClient:
    """Async Gemini client for streaming chat and tool calling."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._model = model
        self._client = genai.Client(api_key=api_key)

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks from Gemini.

        Yields text delta strings as they arrive.
        """
        contents = convert_messages_to_gemini(messages)
        gemini_tool = convert_tools_to_gemini(tools or [])

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )
        if gemini_tool:
            config.tools = [gemini_tool]

        try:
            async for chunk in self._client.aio.models.generate_content_stream(
                model=self._model,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception:
            logger.exception("Gemini streaming error")
            yield "I'm sorry, I encountered an error processing your request. Please try again."

    async def chat_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Non-streaming call that may return tool calls.

        Returns:
            {
                "text": "...",           # any text content
                "tool_calls": [          # list of tool call requests
                    {"name": "...", "args": {...}},
                ],
            }
        """
        contents = convert_messages_to_gemini(messages)
        gemini_tool = convert_tools_to_gemini(tools)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )
        if gemini_tool:
            config.tools = [gemini_tool]

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
        except Exception:
            logger.exception("Gemini tool call error")
            return {
                "text": "I'm sorry, I encountered an error processing your request. Please try again.",
                "tool_calls": [],
            }

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    text_parts.append(part.text)
                elif part.function_call:
                    fc = part.function_call
                    # Convert args from proto MapComposite to plain dict
                    args = dict(fc.args) if fc.args else {}
                    # Ensure values are JSON-serializable primitives
                    clean_args: dict[str, Any] = {}
                    for k, v in args.items():
                        try:
                            json.dumps(v)
                            clean_args[k] = v
                        except (TypeError, ValueError):
                            clean_args[k] = str(v)
                    tool_calls.append({
                        "name": fc.name,
                        "args": clean_args,
                    })

        return {
            "text": "".join(text_parts),
            "tool_calls": tool_calls,
        }
