"""Copilot service: session management + agent orchestration + model management."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.a2ui.protocol import A2UIEvent, done_event, text_delta
from lingshu.copilot.a2ui.renderer import A2UIRenderer
from lingshu.copilot.agent.context import build_context
from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.agent.providers import LLMProvider, create_provider
from lingshu.copilot.agent.state import CopilotState
from lingshu.copilot.infra.mcp import McpManager
from lingshu.copilot.infra.models import ModelManager
from lingshu.copilot.infra.skills import SkillManager
from lingshu.copilot.infra.subagents import SubAgentManager
from lingshu.copilot.models import (
    CopilotModel, CopilotSession, CopilotSkill, McpConnection, SubAgent,
)
from lingshu.copilot.schemas.responses import (
    CopilotOverviewResponse,
    McpConnectionResponse,
    ModelResponse,
    SessionResponse,
    SkillResponse,
    SubAgentResponse,
)
from lingshu.copilot.sessions.manager import SessionManager
from lingshu.config import Settings
from lingshu.function.interface import FunctionService
from lingshu.infra.errors import AppError


class CopilotServiceImpl:
    """Copilot service implementation."""

    def __init__(
        self,
        function_service: FunctionService,
        settings: Settings | None = None,
    ) -> None:
        self._function = function_service
        self._session_manager = SessionManager()
        self._model_manager = ModelManager()
        self._skill_manager = SkillManager()
        self._mcp_manager = McpManager()
        self._subagent_manager = SubAgentManager()
        # Build LLM provider: prefer copilot_* settings, fall back to gemini_*
        llm_provider = self._build_llm_provider(settings)
        self._agent = AgentGraph(
            function_service=function_service,
            llm_provider=llm_provider,
        )
        self._renderer = A2UIRenderer()

    @staticmethod
    def _build_llm_provider(settings: Settings | None) -> LLMProvider | None:
        """Build LLM provider from settings, preferring copilot_* over gemini_*."""
        if settings is None:
            return None

        # New copilot_* settings take precedence
        if settings.copilot_api_key:
            provider_type = settings.copilot_provider or "gemini"
            model = settings.copilot_model or settings.gemini_model
            try:
                return create_provider(provider_type, settings.copilot_api_key, model)
            except (ValueError, ImportError):
                logger.warning(
                    "Failed to create %s provider, falling back", provider_type,
                )

        # Legacy gemini_* fallback
        if settings.gemini_api_key:
            try:
                return create_provider(
                    "gemini", settings.gemini_api_key, settings.gemini_model,
                )
            except (ValueError, ImportError):
                logger.warning("Failed to create Gemini provider")

        return None

    # ── Session Management ───────────────────────────────────────

    async def create_session(
        self,
        mode: str,
        context: dict[str, Any],
        db_session: AsyncSession,
    ) -> SessionResponse:
        copilot_session = await self._session_manager.create_session(
            db_session, mode=mode, context=context,
        )
        return self._session_to_response(copilot_session)

    async def get_session(
        self, session_id: str, db_session: AsyncSession,
    ) -> SessionResponse:
        copilot_session = await self._session_manager.get_session(
            session_id, db_session,
        )
        return self._session_to_response(copilot_session)

    async def query_sessions(
        self,
        db_session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SessionResponse], int]:
        sessions, total = await self._session_manager.query_sessions(
            db_session, offset=offset, limit=limit,
        )
        return [self._session_to_response(s) for s in sessions], total

    async def update_context(
        self,
        session_id: str,
        context: dict[str, Any],
        db_session: AsyncSession,
    ) -> SessionResponse:
        copilot_session = await self._session_manager.update_context(
            session_id, context, db_session,
        )
        return self._session_to_response(copilot_session)

    async def delete_session(
        self, session_id: str, db_session: AsyncSession,
    ) -> None:
        await self._session_manager.delete_session(session_id, db_session)

    # ── Message Processing ───────────────────────────────────────

    async def send_message(
        self,
        session_id: str,
        content: str,
        db_session: AsyncSession,
    ) -> AsyncGenerator[A2UIEvent]:
        """Process a message and yield SSE events."""
        # Get session
        copilot_session = await self._session_manager.get_session(
            session_id, db_session,
        )

        # Build agent state
        session_context = build_context(
            copilot_session.mode, copilot_session.context,
        )
        state = CopilotState(
            messages=[],
            context=session_context,
        )

        # Auto-generate title from first message
        if not copilot_session.title:
            title = content[:50] + ("..." if len(content) > 50 else "")
            await self._session_manager.update_title(
                session_id, title, db_session,
            )

        # Process through agent
        try:
            events = await self._agent.process_message(
                state, content, db_session,
            )
            for event in events:
                event_type = event.get("type", "")
                if event_type == "interrupt":
                    # Store the interrupt context in session
                    confirmation = event.get("confirmation", {})
                    new_context = {
                        **(copilot_session.context or {}),
                        "_pending_interrupt": confirmation,
                    }
                    await self._session_manager.update_context(
                        session_id, new_context, db_session,
                    )
                    yield self._renderer.render_interrupt(confirmation)
                    return  # Stop processing, wait for resume
                if event_type == "text_delta":
                    yield self._renderer.render_text_chunk(
                        event.get("content", ""),
                    )
                elif event_type == "component":
                    yield self._renderer.render_component(
                        event.get("component", {}),
                    )
                elif event_type == "tool_start":
                    yield self._renderer.render_tool_start(
                        event.get("tool_name", ""),
                        event.get("params", {}),
                    )
                elif event_type == "tool_end":
                    yield self._renderer.render_tool_end(
                        event.get("tool_name", ""),
                        event.get("status", "success"),
                    )
            yield self._renderer.render_done()
        except AppError as e:
            yield self._renderer.render_error(e.message)
            yield self._renderer.render_done()
        except Exception as e:
            yield self._renderer.render_error(str(e))
            yield self._renderer.render_done()

        # Update last active
        await self._session_manager.touch(session_id, db_session)

    async def resume_execution(
        self,
        session_id: str,
        approved: bool,
        db_session: AsyncSession,
    ) -> AsyncGenerator[A2UIEvent]:
        """Resume an interrupted agent execution with proper action handling."""
        session = await self._session_manager.get_session(
            session_id, db_session,
        )
        pending = (session.context or {}).get("_pending_interrupt")

        if not pending:
            yield text_delta("No pending operation to resume.", 1)
            yield done_event(2)
            return

        # Clear pending interrupt from context (immutable: build new dict)
        new_context = {
            k: v
            for k, v in (session.context or {}).items()
            if k != "_pending_interrupt"
        }
        await self._session_manager.update_context(
            session_id, new_context, db_session,
        )

        renderer = A2UIRenderer()

        if approved:
            execution_id = pending.get("execution_id")

            yield renderer.render_text_chunk("Operation approved. Executing...")

            if execution_id:
                # Confirm via FunctionService
                try:
                    result = await self._function.confirm_execution(
                        execution_id, db_session,
                    )
                    status = result.status if hasattr(result, "status") else "success"
                    yield renderer.render_text_chunk(
                        f" Execution completed: {status}",
                    )
                except AppError as e:
                    yield renderer.render_error(e.message)
                except Exception as e:
                    yield renderer.render_error(str(e))

            yield renderer.render_done()
        else:
            execution_id = pending.get("execution_id")
            if execution_id:
                try:
                    await self._function.cancel_execution(
                        execution_id, db_session,
                    )
                except Exception:
                    pass  # Best-effort cancellation
            yield renderer.render_text_chunk("Operation cancelled by user.")
            yield renderer.render_done()

        await self._session_manager.touch(session_id, db_session)

    # ── Model Management ─────────────────────────────────────────

    async def register_model(
        self,
        api_name: str,
        display_name: str,
        provider: str,
        connection: dict[str, Any],
        parameters: dict[str, Any],
        is_default: bool,
        db_session: AsyncSession,
    ) -> ModelResponse:
        model = await self._model_manager.register(
            db_session,
            api_name=api_name,
            display_name=display_name,
            provider=provider,
            connection=connection,
            parameters=parameters,
            is_default=is_default,
        )
        return self._model_to_response(model)

    async def get_model(
        self, rid: str, db_session: AsyncSession,
    ) -> ModelResponse:
        model = await self._model_manager.get(rid, db_session)
        return self._model_to_response(model)

    async def update_model(
        self, rid: str, updates: dict[str, Any], db_session: AsyncSession,
    ) -> ModelResponse:
        model = await self._model_manager.update(rid, updates, db_session)
        return self._model_to_response(model)

    async def delete_model(
        self, rid: str, db_session: AsyncSession,
    ) -> None:
        await self._model_manager.delete(rid, db_session)

    async def query_models(
        self,
        db_session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ModelResponse], int]:
        models, total = await self._model_manager.query(
            db_session, offset=offset, limit=limit,
        )
        return [self._model_to_response(m) for m in models], total

    # ── Skill Management ───────────────────────────────────────────

    async def register_skill(
        self,
        api_name: str,
        display_name: str,
        description: str | None,
        system_prompt: str,
        tool_bindings: list[dict[str, Any]],
        db_session: AsyncSession,
    ) -> SkillResponse:
        skill = await self._skill_manager.register(
            db_session,
            api_name=api_name,
            display_name=display_name,
            description=description,
            system_prompt=system_prompt,
            tool_bindings=tool_bindings,
        )
        return self._skill_to_response(skill)

    async def get_skill(
        self, rid: str, db_session: AsyncSession,
    ) -> SkillResponse:
        skill = await self._skill_manager.get(rid, db_session)
        return self._skill_to_response(skill)

    async def update_skill(
        self, rid: str, updates: dict[str, Any], db_session: AsyncSession,
    ) -> SkillResponse:
        skill = await self._skill_manager.update(rid, updates, db_session)
        return self._skill_to_response(skill)

    async def delete_skill(
        self, rid: str, db_session: AsyncSession,
    ) -> None:
        await self._skill_manager.delete(rid, db_session)

    async def query_skills(
        self,
        db_session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SkillResponse], int]:
        skills, total = await self._skill_manager.query(
            db_session, offset=offset, limit=limit,
        )
        return [self._skill_to_response(s) for s in skills], total

    async def set_skill_enabled(
        self,
        rid: str,
        enabled: bool,
        db_session: AsyncSession,
    ) -> SkillResponse:
        skill = await self._skill_manager.set_enabled(rid, enabled, db_session)
        return self._skill_to_response(skill)

    # ── Sub-Agent Management ────────────────────────────────────────

    async def create_sub_agent(
        self,
        api_name: str,
        display_name: str,
        description: str | None,
        model_rid: str | None,
        system_prompt: str | None,
        tool_bindings: list[dict[str, Any]],
        safety_policy: dict[str, Any],
        enabled: bool,
        db_session: AsyncSession,
    ) -> SubAgentResponse:
        agent = await self._subagent_manager.register(
            db_session,
            api_name=api_name,
            display_name=display_name,
            description=description,
            model_rid=model_rid,
            system_prompt=system_prompt,
            tool_bindings=tool_bindings,
            safety_policy=safety_policy,
            enabled=enabled,
        )
        return self._subagent_to_response(agent)

    async def get_sub_agent(
        self, rid: str, db_session: AsyncSession,
    ) -> SubAgentResponse:
        agent = await self._subagent_manager.get(rid, db_session)
        return self._subagent_to_response(agent)

    async def update_sub_agent(
        self, rid: str, updates: dict[str, Any], db_session: AsyncSession,
    ) -> SubAgentResponse:
        agent = await self._subagent_manager.update(rid, updates, db_session)
        return self._subagent_to_response(agent)

    async def delete_sub_agent(
        self, rid: str, db_session: AsyncSession,
    ) -> None:
        await self._subagent_manager.delete(rid, db_session)

    async def query_sub_agents(
        self,
        db_session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SubAgentResponse], int]:
        agents, total = await self._subagent_manager.query(
            db_session, offset=offset, limit=limit,
        )
        return [self._subagent_to_response(a) for a in agents], total

    # ── MCP Management ────────────────────────────────────────────

    async def connect_mcp(
        self,
        api_name: str,
        display_name: str,
        description: str | None,
        transport: dict[str, Any],
        auth: dict[str, Any] | None,
        db_session: AsyncSession,
    ) -> McpConnectionResponse:
        conn = await self._mcp_manager.connect(
            db_session,
            api_name=api_name,
            display_name=display_name,
            description=description,
            transport=transport,
            auth=auth,
        )
        return self._mcp_to_response(conn)

    async def get_mcp(
        self, rid: str, db_session: AsyncSession,
    ) -> McpConnectionResponse:
        conn = await self._mcp_manager.get(rid, db_session)
        return self._mcp_to_response(conn)

    async def update_mcp(
        self, rid: str, updates: dict[str, Any], db_session: AsyncSession,
    ) -> McpConnectionResponse:
        conn = await self._mcp_manager.update(rid, updates, db_session)
        return self._mcp_to_response(conn)

    async def delete_mcp(
        self, rid: str, db_session: AsyncSession,
    ) -> None:
        await self._mcp_manager.delete(rid, db_session)

    async def query_mcp(
        self,
        db_session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[McpConnectionResponse], int]:
        conns, total = await self._mcp_manager.query(
            db_session, offset=offset, limit=limit,
        )
        return [self._mcp_to_response(c) for c in conns], total

    async def discover_mcp_tools(
        self, rid: str, db_session: AsyncSession,
    ) -> list[dict[str, Any]]:
        return await self._mcp_manager.discover_tools(rid, db_session)

    async def test_mcp_connection(
        self, rid: str, db_session: AsyncSession,
    ) -> dict[str, Any]:
        return await self._mcp_manager.test_connection(rid, db_session)

    # ── Overview ─────────────────────────────────────────────────

    async def get_overview(
        self, db_session: AsyncSession,
    ) -> CopilotOverviewResponse:
        _, session_total = await self._session_manager.query_sessions(
            db_session, limit=1,
        )
        _, model_total = await self._model_manager.query(
            db_session, limit=1,
        )
        return CopilotOverviewResponse(
            sessions={"total": session_total},
            models={"total": model_total},
        )

    # ── Helpers ───────────────────────────────────────────────────

    def _session_to_response(self, s: CopilotSession) -> SessionResponse:
        return SessionResponse(
            session_id=s.session_id,
            mode=s.mode,
            title=s.title,
            context=s.context,
            model_rid=s.model_rid,
            status=s.status,
            created_at=s.created_at,
            last_active_at=s.last_active_at,
        )

    def _model_to_response(self, m: CopilotModel) -> ModelResponse:
        return ModelResponse(
            rid=m.rid,
            api_name=m.api_name,
            display_name=m.display_name,
            provider=m.provider,
            connection=m.connection,
            parameters=m.parameters,
            is_default=m.is_default,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def _skill_to_response(self, s: CopilotSkill) -> SkillResponse:
        return SkillResponse(
            rid=s.rid,
            api_name=s.api_name,
            display_name=s.display_name,
            description=s.description,
            system_prompt=s.system_prompt or "",
            tool_bindings=s.tool_bindings,
            enabled=s.enabled,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )

    def _mcp_to_response(self, c: McpConnection) -> McpConnectionResponse:
        return McpConnectionResponse(
            rid=c.rid,
            api_name=c.api_name,
            display_name=c.display_name,
            description=c.description,
            transport=c.transport,
            auth=c.auth,
            discovered_tools=c.discovered_tools,
            status=c.status,
            enabled=c.enabled,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )

    def _subagent_to_response(self, a: SubAgent) -> SubAgentResponse:
        return SubAgentResponse(
            rid=a.rid,
            api_name=a.api_name,
            display_name=a.display_name,
            description=a.description,
            model_rid=a.model_rid,
            system_prompt=a.system_prompt,
            tool_bindings=a.tool_bindings,
            safety_policy=a.safety_policy,
            enabled=a.enabled,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
