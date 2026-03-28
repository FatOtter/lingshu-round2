"""BS-04: Copilot Conversation with A2UI Rendering.

Scenario: A business analyst uses the Copilot to query data,
receiving streaming SSE responses with A2UI components.

Steps:
1. Create session
2. Send message
3. Agent processes and calls tools
4. A2UI renderer converts to events
5. Verify SSE event structure
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.a2ui.protocol import A2UIEvent
from lingshu.copilot.models import CopilotSession
from lingshu.copilot.service import CopilotServiceImpl
from lingshu.infra.errors import AppError

from .conftest import mock_session


def _make_copilot_session(
    session_id: str = "ri.session.test1",
    mode: str = "chat",
    title: str | None = None,
    context: dict[str, Any] | None = None,
) -> CopilotSession:
    s = CopilotSession(
        session_id=session_id,
        tenant_id="ri.tenant.test-tenant",
        user_id="ri.user.admin",
        mode=mode,
        title=title,
        context=context or {},
        status="active",
    )
    s.created_at = datetime.now(UTC)
    s.last_active_at = datetime.now(UTC)
    return s


def _build_service() -> CopilotServiceImpl:
    function_service = AsyncMock()
    return CopilotServiceImpl(function_service=function_service)


class TestCopilotConversation:
    """Complete Copilot conversation scenario with A2UI rendering."""

    async def test_step1_create_session(self) -> None:
        """Step 1: Create a new Copilot session."""
        service = _build_service()
        session = mock_session()
        copilot_session = _make_copilot_session()

        service._session_manager.create_session = AsyncMock(
            return_value=copilot_session,
        )

        with (
            patch("lingshu.copilot.sessions.manager.get_tenant_id", return_value="t1"),
            patch("lingshu.copilot.sessions.manager.get_user_id", return_value="u1"),
        ):
            result = await service.create_session("chat", {}, session)
            assert result.session_id == "ri.session.test1"
            assert result.mode == "chat"
            assert result.status == "active"

    async def test_step2_send_message_with_text_response(self) -> None:
        """Step 2: Send a message and receive text delta events."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(title="Test Chat")

        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()

        # Agent returns text delta events
        service._agent.process_message = AsyncMock(
            return_value=[
                {"type": "text_delta", "content": "Here are the traffic lights:"},
                {"type": "text_delta", "content": " TL-001, TL-002, TL-003"},
            ],
        )

        events: list[A2UIEvent] = []
        async for event in service.send_message(
            "ri.session.test1", "List all traffic lights", db_session,
        ):
            events.append(event)

        # Should have text deltas + done event
        text_events = [e for e in events if e.event_type == "text_delta"]
        done_events = [e for e in events if e.event_type == "done"]
        assert len(text_events) >= 1
        assert len(done_events) == 1

    async def test_step3_agent_calls_tools(self) -> None:
        """Step 3: Agent processes message with tool calls."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(title="Tool Call Test")

        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()

        # Agent returns tool_start, tool_end, then text events
        service._agent.process_message = AsyncMock(
            return_value=[
                {"type": "tool_start", "tool_name": "query_instances", "params": {}},
                {"type": "tool_end", "tool_name": "query_instances", "status": "success"},
                {"type": "text_delta", "content": "Found 3 traffic lights."},
            ],
        )

        events: list[A2UIEvent] = []
        async for event in service.send_message(
            "ri.session.test1", "How many traffic lights?", db_session,
        ):
            events.append(event)

        tool_starts = [e for e in events if e.event_type == "tool_start"]
        tool_ends = [e for e in events if e.event_type == "tool_end"]
        assert len(tool_starts) == 1
        assert len(tool_ends) == 1

    async def test_step4_a2ui_component_rendering(self) -> None:
        """Step 4: A2UI renderer produces component events."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(title="Component Test")

        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()

        # Agent returns component event
        service._agent.process_message = AsyncMock(
            return_value=[
                {
                    "type": "component",
                    "component": {
                        "type": "table",
                        "columns": ["id", "name", "status"],
                        "rows": [
                            [1, "TL-001", "active"],
                            [2, "TL-002", "offline"],
                        ],
                    },
                },
            ],
        )

        events: list[A2UIEvent] = []
        async for event in service.send_message(
            "ri.session.test1", "Show traffic light table", db_session,
        ):
            events.append(event)

        component_events = [e for e in events if e.event_type == "component"]
        assert len(component_events) == 1

    async def test_step5_interrupt_and_resume(self) -> None:
        """Step 5: Agent triggers interrupt, user confirms."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(title="Interrupt Test")

        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.update_context = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()

        # Agent returns interrupt event
        service._agent.process_message = AsyncMock(
            return_value=[
                {
                    "type": "interrupt",
                    "confirmation": {
                        "execution_id": "exec_abc",
                        "message": "This will restart the device",
                        "safety_level": "SAFETY_NON_IDEMPOTENT",
                    },
                },
            ],
        )

        events: list[A2UIEvent] = []
        async for event in service.send_message(
            "ri.session.test1", "Restart TL-001", db_session,
        ):
            events.append(event)

        interrupt_events = [e for e in events if e.event_type == "interrupt"]
        assert len(interrupt_events) == 1

    async def test_resume_approved(self) -> None:
        """Resume execution after approval."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(
            title="Resume Test",
            context={
                "_pending_interrupt": {
                    "execution_id": "exec_abc",
                    "message": "Restart device",
                },
            },
        )

        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.update_context = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()

        confirm_result = MagicMock()
        confirm_result.status = "success"
        service._function.confirm_execution = AsyncMock(return_value=confirm_result)

        events: list[A2UIEvent] = []
        async for event in service.resume_execution(
            "ri.session.test1", approved=True, db_session=db_session,
        ):
            events.append(event)

        text_events = [e for e in events if e.event_type == "text_delta"]
        assert any(
            "approved" in str(e.data).lower() or "executing" in str(e.data).lower()
            for e in text_events
        )

    async def test_resume_rejected(self) -> None:
        """Resume execution with rejection."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(
            title="Reject Test",
            context={
                "_pending_interrupt": {
                    "execution_id": "exec_abc",
                    "message": "Restart device",
                },
            },
        )

        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.update_context = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()
        service._function.cancel_execution = AsyncMock()

        events: list[A2UIEvent] = []
        async for event in service.resume_execution(
            "ri.session.test1", approved=False, db_session=db_session,
        ):
            events.append(event)

        text_events = [e for e in events if e.event_type == "text_delta"]
        assert any("cancel" in str(e.data).lower() for e in text_events)

    async def test_error_handling_in_message(self) -> None:
        """Agent error produces error event followed by done."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(title="Error Test")
        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()

        service._agent.process_message = AsyncMock(
            side_effect=Exception("LLM unavailable"),
        )

        events: list[A2UIEvent] = []
        async for event in service.send_message(
            "ri.session.test1", "broken request", db_session,
        ):
            events.append(event)

        error_events = [e for e in events if e.event_type == "error"]
        done_events = [e for e in events if e.event_type == "done"]
        assert len(error_events) == 1
        assert len(done_events) == 1

    async def test_auto_title_on_first_message(self) -> None:
        """Auto-generate title from first message."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(title=None)
        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.update_title = AsyncMock()
        service._session_manager.touch = AsyncMock()
        service._agent.process_message = AsyncMock(return_value=[])

        events = []
        async for event in service.send_message(
            "ri.session.test1", "List all traffic lights", db_session,
        ):
            events.append(event)

        service._session_manager.update_title.assert_awaited_once()
