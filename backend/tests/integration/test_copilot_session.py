"""Integration tests for copilot session flows: create, message, interrupt, resume."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.models import CopilotSession
from lingshu.copilot.service import CopilotServiceImpl
from lingshu.infra.errors import AppError, ErrorCode


# ── Helpers ───────────────────────────────────────────────────────


def _make_session(
    session_id: str = "sess_1",
    mode: str = "shell",
    context: dict[str, Any] | None = None,
    title: str | None = None,
) -> CopilotSession:
    s = CopilotSession(
        session_id=session_id,
        tenant_id="t1",
        user_id="u1",
        mode=mode,
        title=title,
        context=context or {},
        model_rid=None,
        status="active",
    )
    s.created_at = datetime.utcnow()
    s.last_active_at = datetime.utcnow()
    return s


def _build_service() -> CopilotServiceImpl:
    function_service = AsyncMock()
    return CopilotServiceImpl(function_service=function_service)


def _mock_session() -> AsyncMock:
    s = AsyncMock()
    s.commit = AsyncMock()
    return s


# ── Tests ─────────────────────────────────────────────────────────


class TestCreateSessionSendMessage:
    """Create session -> send message -> get response events."""

    async def test_full_flow(self) -> None:
        service = _build_service()
        db_session = _mock_session()
        copilot_sess = _make_session()

        service._session_manager.create_session = AsyncMock(return_value=copilot_sess)
        service._session_manager.get_session = AsyncMock(return_value=copilot_sess)
        service._session_manager.update_title = AsyncMock()
        service._session_manager.touch = AsyncMock()

        # Mock agent to return text events
        service._agent.process_message = AsyncMock(return_value=[
            {"type": "text_delta", "content": "Hello!"},
            {"type": "text_delta", "content": " How can I help?"},
        ])

        # Create
        result = await service.create_session("shell", {}, db_session)
        assert result.session_id == "sess_1"
        assert result.mode == "shell"

        # Send message and collect events
        events = []
        async for event in service.send_message("sess_1", "Hi there", db_session):
            events.append(event)

        # Should have text events + done
        assert len(events) >= 2
        service._session_manager.touch.assert_awaited()


class TestShellModeContextFiltering:
    """Shell mode session should pass mode-specific context."""

    async def test_shell_context(self) -> None:
        service = _build_service()
        db_session = _mock_session()
        copilot_sess = _make_session(
            mode="shell",
            context={"object_type_rid": "ri.obj.1", "view_id": "v1"},
        )

        service._session_manager.get_session = AsyncMock(return_value=copilot_sess)
        service._session_manager.update_title = AsyncMock()
        service._session_manager.touch = AsyncMock()

        captured_state = None
        original_process = service._agent.process_message

        async def _capture_state(state: Any, content: str, session: Any) -> list[dict[str, Any]]:
            nonlocal captured_state
            captured_state = state
            return [{"type": "text_delta", "content": "ok"}]

        service._agent.process_message = _capture_state  # type: ignore[assignment]

        events = []
        async for event in service.send_message("sess_1", "query data", db_session):
            events.append(event)

        assert captured_state is not None
        assert captured_state["context"] is not None


class TestInterruptResume:
    """Interrupt -> resume with approve."""

    async def test_interrupt_then_approve(self) -> None:
        service = _build_service()
        db_session = _mock_session()
        copilot_sess = _make_session()

        service._session_manager.get_session = AsyncMock(return_value=copilot_sess)
        service._session_manager.update_title = AsyncMock()
        service._session_manager.update_context = AsyncMock(return_value=copilot_sess)
        service._session_manager.touch = AsyncMock()

        # Agent returns an interrupt event
        service._agent.process_message = AsyncMock(return_value=[
            {"type": "interrupt", "confirmation": {
                "execution_id": "exec_123",
                "message": "This will delete data",
                "safety_level": "SAFETY_NON_IDEMPOTENT",
            }},
        ])

        # Send message - should yield interrupt event
        events = []
        async for event in service.send_message("sess_1", "delete all robots", db_session):
            events.append(event)

        # Should have stored interrupt context
        service._session_manager.update_context.assert_awaited()

        # Now resume with approval
        resumed_sess = _make_session(context={
            "_pending_interrupt": {
                "execution_id": "exec_123",
                "message": "This will delete data",
            },
        })
        service._session_manager.get_session = AsyncMock(return_value=resumed_sess)
        service._function.confirm_execution = AsyncMock(
            return_value=MagicMock(status="success"),
        )

        resume_events = []
        async for event in service.resume_execution("sess_1", True, db_session):
            resume_events.append(event)

        assert len(resume_events) >= 2  # text + done
        service._function.confirm_execution.assert_awaited_once_with("exec_123", db_session)

    async def test_interrupt_then_reject(self) -> None:
        service = _build_service()
        db_session = _mock_session()

        resumed_sess = _make_session(context={
            "_pending_interrupt": {
                "execution_id": "exec_456",
                "message": "Dangerous op",
            },
        })
        service._session_manager.get_session = AsyncMock(return_value=resumed_sess)
        service._session_manager.update_context = AsyncMock(return_value=resumed_sess)
        service._session_manager.touch = AsyncMock()
        service._function.cancel_execution = AsyncMock()

        events = []
        async for event in service.resume_execution("sess_1", False, db_session):
            events.append(event)

        assert len(events) >= 1
        service._function.cancel_execution.assert_awaited_once()


class TestResumeNoPending:
    """Resume when no interrupt is pending."""

    async def test_no_pending(self) -> None:
        service = _build_service()
        db_session = _mock_session()
        copilot_sess = _make_session(context={})

        service._session_manager.get_session = AsyncMock(return_value=copilot_sess)
        service._session_manager.touch = AsyncMock()

        events = []
        async for event in service.resume_execution("sess_1", True, db_session):
            events.append(event)

        assert len(events) >= 1  # "No pending" + done


class TestSubAgentToolLoading:
    """Create sub-agent -> verify tool bindings are registered."""

    async def test_create_sub_agent(self) -> None:
        service = _build_service()
        db_session = _mock_session()

        mock_agent = MagicMock()
        mock_agent.rid = "ri.agent.1"
        mock_agent.api_name = "data_analyst"
        mock_agent.display_name = "Data Analyst"
        mock_agent.description = "Analyzes data"
        mock_agent.model_rid = None
        mock_agent.system_prompt = "You are a data analyst"
        mock_agent.tool_bindings = [{"tool": "query_instances", "enabled": True}]
        mock_agent.safety_policy = {"max_tool_calls": 10}
        mock_agent.enabled = True
        mock_agent.created_at = datetime.utcnow()
        mock_agent.updated_at = datetime.utcnow()

        service._subagent_manager.register = AsyncMock(return_value=mock_agent)

        result = await service.create_sub_agent(
            api_name="data_analyst",
            display_name="Data Analyst",
            description="Analyzes data",
            model_rid=None,
            system_prompt="You are a data analyst",
            tool_bindings=[{"tool": "query_instances", "enabled": True}],
            safety_policy={"max_tool_calls": 10},
            enabled=True,
            db_session=db_session,
        )
        assert result.api_name == "data_analyst"
        assert len(result.tool_bindings) == 1


class TestSessionAutoTitle:
    """First message should auto-generate session title."""

    async def test_auto_title(self) -> None:
        service = _build_service()
        db_session = _mock_session()
        copilot_sess = _make_session(title=None)

        service._session_manager.get_session = AsyncMock(return_value=copilot_sess)
        service._session_manager.update_title = AsyncMock()
        service._session_manager.touch = AsyncMock()
        service._agent.process_message = AsyncMock(return_value=[
            {"type": "text_delta", "content": "Response"},
        ])

        events = []
        async for event in service.send_message("sess_1", "What is the meaning of life?", db_session):
            events.append(event)

        service._session_manager.update_title.assert_awaited_once()
        title_arg = service._session_manager.update_title.call_args[0][1]
        assert "What is the meaning" in title_arg
