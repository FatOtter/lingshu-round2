"""Unit tests for human-in-the-loop interrupt/resume flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.a2ui.renderer import A2UIRenderer
from lingshu.copilot.service import CopilotServiceImpl


def _make_mock_session(
    *,
    context: dict[str, Any] | None = None,
    session_id: str = "session-1",
    mode: str = "agent",
    title: str = "Test",
) -> MagicMock:
    """Build a mock CopilotSession."""
    session = MagicMock()
    session.session_id = session_id
    session.mode = mode
    session.title = title
    session.context = context or {}
    session.model_rid = None
    session.status = "active"
    session.created_at = None
    session.last_active_at = None
    return session


def _make_service(
    function_service: Any = None,
) -> CopilotServiceImpl:
    """Build a CopilotServiceImpl with mocked dependencies."""
    if function_service is None:
        function_service = MagicMock()
    return CopilotServiceImpl(function_service)


class TestResumeWithNoPending:
    """Test resume when no pending interrupt exists."""

    @pytest.mark.asyncio
    async def test_no_pending_interrupt(self) -> None:
        mock_fn = MagicMock()
        service = _make_service(mock_fn)

        mock_session = _make_mock_session(context={})
        with patch.object(
            service._session_manager,
            "get_session",
            new_callable=AsyncMock,
            return_value=mock_session,
        ):
            events = []
            async for event in service.resume_execution(
                "session-1", True, AsyncMock(),
            ):
                events.append(event)

        assert len(events) == 2
        assert events[0].event_type == "text_delta"
        assert "No pending operation" in events[0].data["content"]
        assert events[1].event_type == "done"


class TestResumeWithApproval:
    """Test resume when user approves the pending action."""

    @pytest.mark.asyncio
    async def test_approved_with_execution_id(self) -> None:
        mock_fn = MagicMock()
        mock_result = MagicMock()
        mock_result.status = "success"
        mock_fn.confirm_execution = AsyncMock(return_value=mock_result)

        service = _make_service(mock_fn)

        pending = {
            "execution_id": "exec-123",
            "action_rid": "ri.action.1",
            "params": {"key": "value"},
        }
        mock_session = _make_mock_session(
            context={"module": "data", "_pending_interrupt": pending},
        )

        db_session = AsyncMock()

        with (
            patch.object(
                service._session_manager,
                "get_session",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "update_context",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "touch",
                new_callable=AsyncMock,
            ),
        ):
            events = []
            async for event in service.resume_execution(
                "session-1", True, db_session,
            ):
                events.append(event)

        # Should have: text_chunk("approved"), text_chunk("completed"), done
        assert any(
            e.event_type == "text_delta" and "approved" in e.data.get("content", "").lower()
            for e in events
        )
        assert any(
            e.event_type == "text_delta" and "success" in e.data.get("content", "").lower()
            for e in events
        )
        assert events[-1].event_type == "done"
        mock_fn.confirm_execution.assert_awaited_once_with("exec-123", db_session)

    @pytest.mark.asyncio
    async def test_approved_without_execution_id(self) -> None:
        mock_fn = MagicMock()
        service = _make_service(mock_fn)

        pending = {"action_rid": "ri.action.1", "params": {}}
        mock_session = _make_mock_session(
            context={"_pending_interrupt": pending},
        )

        with (
            patch.object(
                service._session_manager,
                "get_session",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "update_context",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "touch",
                new_callable=AsyncMock,
            ),
        ):
            events = []
            async for event in service.resume_execution(
                "session-1", True, AsyncMock(),
            ):
                events.append(event)

        assert any(
            e.event_type == "text_delta" and "approved" in e.data.get("content", "").lower()
            for e in events
        )
        assert events[-1].event_type == "done"


class TestResumeWithRejection:
    """Test resume when user rejects the pending action."""

    @pytest.mark.asyncio
    async def test_rejected_with_execution_id(self) -> None:
        mock_fn = MagicMock()
        mock_fn.cancel_execution = AsyncMock(return_value=MagicMock())

        service = _make_service(mock_fn)

        pending = {"execution_id": "exec-456", "action_rid": "ri.action.2"}
        mock_session = _make_mock_session(
            context={"_pending_interrupt": pending},
        )

        db_session = AsyncMock()

        with (
            patch.object(
                service._session_manager,
                "get_session",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "update_context",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "touch",
                new_callable=AsyncMock,
            ),
        ):
            events = []
            async for event in service.resume_execution(
                "session-1", False, db_session,
            ):
                events.append(event)

        assert any(
            e.event_type == "text_delta" and "cancelled" in e.data.get("content", "").lower()
            for e in events
        )
        assert events[-1].event_type == "done"
        mock_fn.cancel_execution.assert_awaited_once_with("exec-456", db_session)

    @pytest.mark.asyncio
    async def test_rejected_without_execution_id(self) -> None:
        mock_fn = MagicMock()
        service = _make_service(mock_fn)

        pending = {"action_rid": "ri.action.3"}
        mock_session = _make_mock_session(
            context={"_pending_interrupt": pending},
        )

        with (
            patch.object(
                service._session_manager,
                "get_session",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "update_context",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "touch",
                new_callable=AsyncMock,
            ),
        ):
            events = []
            async for event in service.resume_execution(
                "session-1", False, AsyncMock(),
            ):
                events.append(event)

        assert any(
            e.event_type == "text_delta" and "cancelled" in e.data.get("content", "").lower()
            for e in events
        )
        assert events[-1].event_type == "done"


class TestResumeContextCleared:
    """Verify pending interrupt is cleared from context after resume."""

    @pytest.mark.asyncio
    async def test_pending_cleared_on_approval(self) -> None:
        mock_fn = MagicMock()
        mock_fn.confirm_execution = AsyncMock(return_value=MagicMock(status="ok"))

        service = _make_service(mock_fn)

        pending = {"execution_id": "exec-789"}
        original_context = {
            "module": "data",
            "page": "/data/objects",
            "_pending_interrupt": pending,
        }
        mock_session = _make_mock_session(context=original_context)

        update_context_mock = AsyncMock(return_value=mock_session)

        with (
            patch.object(
                service._session_manager,
                "get_session",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch.object(
                service._session_manager,
                "update_context",
                new=update_context_mock,
            ),
            patch.object(
                service._session_manager,
                "touch",
                new_callable=AsyncMock,
            ),
        ):
            events = []
            async for event in service.resume_execution(
                "session-1", True, AsyncMock(),
            ):
                events.append(event)

        # Verify update_context was called with context that excludes _pending_interrupt
        update_context_mock.assert_awaited_once()
        call_args = update_context_mock.call_args
        new_ctx = call_args[0][1]  # second positional arg is context
        assert "_pending_interrupt" not in new_ctx
        assert new_ctx["module"] == "data"
        assert new_ctx["page"] == "/data/objects"


class TestRendererInterrupt:
    """Test the A2UIRenderer.render_interrupt method."""

    def test_render_interrupt(self) -> None:
        renderer = A2UIRenderer()
        confirmation = {
            "action_rid": "ri.action.1",
            "execution_id": "exec-1",
            "description": "Delete 5 records",
        }
        event = renderer.render_interrupt(confirmation)
        assert event.event_type == "interrupt"
        assert event.data["confirmation"] == confirmation
        assert event.event_id == 1

    def test_render_interrupt_increments_counter(self) -> None:
        renderer = A2UIRenderer()
        renderer.render_text_chunk("hi")
        event = renderer.render_interrupt({"test": True})
        assert event.event_id == 2
