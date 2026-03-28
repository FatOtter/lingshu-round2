"""LangGraph Agent graph definition (P1 + P3 sub-agent orchestration)."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.agent.prompts import build_system_prompt
from lingshu.copilot.agent.providers import LLMProvider, create_provider
from lingshu.copilot.agent.state import CopilotState, SessionContext
from lingshu.copilot.agent.tools import (
    build_tool_schemas,
    execute_tool_call,
    filter_capabilities_for_shell,
)
from lingshu.copilot.infra.subagents import SubAgentManager, load_as_tool
from lingshu.function.interface import FunctionService
from lingshu.function.schemas.responses import CapabilityDescriptor

logger = logging.getLogger(__name__)

_MAX_AGENT_ITERATIONS = 10


class AgentGraph:
    """Agent graph for P1 + P3 sub-agent orchestration.

    Integrates tool discovery, shell mode filtering, human-in-the-loop,
    and sub-agent delegation.
    When an LLM provider is configured, uses the real LLM for responses.
    Falls back to structured guidance responses otherwise.
    """

    def __init__(
        self,
        function_service: FunctionService | None = None,
        *,
        llm_provider: LLMProvider | None = None,
        # Backward compatibility: accept gemini_api_key directly
        gemini_api_key: str = "",
        gemini_model: str = "gemini-2.0-flash",
    ) -> None:
        self._function_service = function_service
        self._subagent_manager = SubAgentManager()
        self._llm: LLMProvider | None = llm_provider

        # Backward compatibility: if llm_provider not given but gemini key is, create one
        if self._llm is None and gemini_api_key:
            self._llm = create_provider(
                "gemini", api_key=gemini_api_key, model=gemini_model,
            )

    def get_system_prompt(self, context: SessionContext) -> str:
        """Get the system prompt for the current session context."""
        return build_system_prompt(context)

    async def get_available_tools(
        self,
        context: SessionContext,
        db_session: AsyncSession,
    ) -> list[CapabilityDescriptor]:
        """Get tools available for the current session context."""
        if self._function_service is None:
            return []

        capabilities = await self._function_service.list_capabilities(db_session)

        mode = context.get("mode", "agent")
        if mode == "shell":
            module = context.get("module", "")
            capabilities = filter_capabilities_for_shell(capabilities, module)

        return capabilities

    async def get_subagent_tools(
        self,
        db_session: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Load enabled sub-agents as callable tool schemas."""
        agents, _ = await self._subagent_manager.query(
            db_session, offset=0, limit=100,
        )
        return [
            load_as_tool(agent)
            for agent in agents
            if agent.enabled
        ]

    async def execute_subagent(
        self,
        subagent_tool: dict[str, Any],
        user_input: str,
        db_session: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Execute a sub-agent as a nested agent run.

        When an LLM provider is configured, performs a nested LLM call using
        the sub-agent's system_prompt and tool_bindings.
        Falls back to informational response when no LLM is available.
        """
        metadata = subagent_tool.get("metadata", {})
        system_prompt = metadata.get("system_prompt", "")
        agent_name = subagent_tool.get("name", "unknown")
        tool_bindings = metadata.get("tool_bindings", [])

        events: list[dict[str, Any]] = []

        events.append({
            "type": "tool_start",
            "tool_name": agent_name,
            "params": {"input": user_input},
        })

        if self._llm is not None:
            # Real nested execution with LLM
            sub_prompt = system_prompt or f"You are {agent_name}, a specialized sub-agent."

            # Build tool schemas from bindings if available
            sub_tools: list[dict[str, Any]] = []
            if tool_bindings and self._function_service and db_session:
                try:
                    capabilities = await self._function_service.list_capabilities(
                        db_session,
                    )
                    # Filter to only bound tools
                    bound_names = {b.get("capability_rid") for b in tool_bindings}
                    filtered = [c for c in capabilities if c.rid in bound_names]
                    sub_tools = build_tool_schemas(filtered)
                except Exception:
                    logger.warning("Failed to load sub-agent tools for %s", agent_name)

            nested_events = await self._process_with_llm(
                sub_prompt,
                user_input,
                sub_tools,
                [],
                db_session,
                "main",
            )

            # Wrap nested events with sub-agent prefix
            for evt in nested_events:
                if evt.get("type") == "text_delta":
                    content = evt.get("content", "")
                    events.append({
                        "type": "text_delta",
                        "content": f"[{agent_name}] {content}",
                    })
                elif evt.get("type") == "done":
                    pass  # Skip nested done; parent controls lifecycle
                else:
                    events.append(evt)
        else:
            # Informational fallback
            prompt_info = (
                f"System prompt length: {len(system_prompt)}"
                if system_prompt
                else "No system prompt configured"
            )
            events.append({
                "type": "text_delta",
                "content": (
                    f"[Sub-Agent: {agent_name}] Processing: {user_input}. "
                    f"{prompt_info}. "
                    f"Tool bindings: {len(tool_bindings)}. "
                    "Full nested agent execution requires model provider configuration."
                ),
            })

        events.append({
            "type": "tool_end",
            "tool_name": agent_name,
            "status": "success",
        })

        return events

    async def _process_with_llm(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        capabilities: list[CapabilityDescriptor],
        db_session: AsyncSession | None,
        branch: str,
    ) -> list[dict[str, Any]]:
        """Process a message using the configured LLM provider with agent loop."""
        assert self._llm is not None

        events: list[dict[str, Any]] = []
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_message},
        ]

        for iteration in range(_MAX_AGENT_ITERATIONS):
            if not tools:
                # No tools: just stream text
                async for chunk in self._llm.chat(
                    system_prompt, messages, tools=None,
                ):
                    events.append({"type": "text_delta", "content": chunk})
                break

            # Call with tools to check if the model wants to use one
            response = await self._llm.chat_with_tools(
                system_prompt, messages, tools,
            )

            tool_calls = response.get("tool_calls", [])
            response_text = response.get("text", "")

            if not tool_calls:
                # No tool calls — emit text and finish
                if response_text:
                    events.append({"type": "text_delta", "content": response_text})
                break

            # Emit any text before tool calls
            if response_text:
                events.append({"type": "text_delta", "content": response_text})

            # Append assistant message with tool calls to conversation
            messages.append({
                "role": "assistant",
                "content": response_text,
                "tool_calls": tool_calls,
            })

            # Execute each tool call
            tool_results: list[dict[str, Any]] = []
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]

                events.append({
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "params": tool_args,
                })

                # Execute via FunctionService
                if self._function_service and db_session:
                    try:
                        result = await execute_tool_call(
                            self._function_service,
                            tool_name,
                            tool_args,
                            capabilities,
                            branch=branch,
                        )
                    except Exception as exc:
                        logger.exception("Tool execution failed: %s", tool_name)
                        result = {"error": str(exc)}
                else:
                    result = {"error": "Function service not available"}

                status = "error" if "error" in result else "success"
                events.append({
                    "type": "tool_end",
                    "tool_name": tool_name,
                    "status": status,
                })

                tool_results.append({
                    "name": tool_name,
                    "result": result,
                })

            # Append tool results to conversation for next iteration
            messages.append({
                "role": "user",
                "tool_results": tool_results,
            })

        events.append({"type": "done"})
        return events

    async def process_message(
        self,
        state: CopilotState,
        user_message: str,
        db_session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """Process user message with tool awareness and sub-agent support.

        When an LLM provider is configured, uses the real LLM for responses.
        Falls back to structured guidance responses otherwise.
        """
        context = state.get("context", SessionContext(mode="agent"))
        system_prompt = self.get_system_prompt(context)
        branch = context.get("branch", "main")

        # Get available tools for context
        tools: list[dict[str, Any]] = []
        capabilities: list[CapabilityDescriptor] = []
        subagent_tools: list[dict[str, Any]] = []
        if db_session and self._function_service:
            capabilities = await self.get_available_tools(context, db_session)
            tools = build_tool_schemas(capabilities)

        # Load sub-agents as tools (requires tenant context)
        if db_session:
            try:
                subagent_tools = await self.get_subagent_tools(db_session)
            except RuntimeError:
                pass  # tenant context not set — skip sub-agent loading

        all_tools = tools + subagent_tools

        # Use real LLM if available
        if self._llm is not None:
            return await self._process_with_llm(
                system_prompt,
                user_message,
                all_tools,
                capabilities,
                db_session,
                branch,
            )

        # Fallback: structured guidance response
        return self._build_fallback_response(
            context, all_tools, subagent_tools, system_prompt, user_message,
        )

    def _build_fallback_response(
        self,
        context: SessionContext,
        all_tools: list[dict[str, Any]],
        subagent_tools: list[dict[str, Any]],
        system_prompt: str,
        user_message: str,
    ) -> list[dict[str, Any]]:
        """Build a helpful structured fallback response when no LLM is configured."""
        events: list[dict[str, Any]] = []
        mode = context.get("mode", "agent")
        module = context.get("module", "")

        # Build guidance message
        parts: list[str] = []
        parts.append(
            "I received your message but cannot generate an AI response yet. "
            "To enable full AI capabilities, please configure a model provider:"
        )
        parts.append("")
        parts.append("**Setup steps:**")
        parts.append(
            "1. Go to Setting -> Agent -> Models to register a model provider"
        )
        parts.append(
            "2. Supported providers: Gemini, OpenAI, Anthropic"
        )
        parts.append(
            "3. Set the environment variables: "
            "LINGSHU_COPILOT_PROVIDER, LINGSHU_COPILOT_API_KEY, LINGSHU_COPILOT_MODEL"
        )

        if all_tools:
            tool_names = [t.get("name", "?") for t in all_tools[:5]]
            remaining = len(all_tools) - len(tool_names)
            tool_list = ", ".join(tool_names)
            if remaining > 0:
                tool_list += f" (+{remaining} more)"
            parts.append("")
            parts.append(f"**Available capabilities ({len(all_tools)}):** {tool_list}")

        if subagent_tools:
            agent_names = [t["name"] for t in subagent_tools]
            parts.append(
                f"**Sub-agents:** {', '.join(agent_names)}"
            )

        mode_label = f"{mode.upper()}"
        if mode == "shell" and module:
            mode_label += f" ({module})"
        parts.append("")
        parts.append(f"Current mode: {mode_label}")

        events.append({
            "type": "text_delta",
            "content": "\n".join(parts),
        })
        events.append({
            "type": "done",
            "system_prompt_length": len(system_prompt),
        })

        return events
