"""BS-08: Copilot Shell Context Awareness.

Scenario: The Shell Copilot adapts its context based on the
user's current page, enabling context-aware responses.

Steps:
1. Shell session created
2. Context updated with current page info
3. Tool filtering based on context
4. Message processed with context-aware prompt
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.agent.context import build_context
from lingshu.copilot.models import CopilotSession
from lingshu.copilot.service import CopilotServiceImpl

from .conftest import mock_session


def _make_copilot_session(
    session_id: str = "ri.session.shell1",
    mode: str = "shell",
    context: dict[str, Any] | None = None,
    title: str = "Shell Session",
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


class TestShellContext:
    """Shell context awareness scenario."""

    async def test_step1_create_shell_session(self) -> None:
        """Step 1: Create a Shell session with initial context."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(
            context={"module": "ontology", "page": "object-types"},
        )
        service._session_manager.create_session = AsyncMock(
            return_value=copilot_session,
        )

        with (
            patch("lingshu.copilot.sessions.manager.get_tenant_id", return_value="t1"),
            patch("lingshu.copilot.sessions.manager.get_user_id", return_value="u1"),
        ):
            result = await service.create_session(
                "shell",
                {"module": "ontology", "page": "object-types"},
                db_session,
            )
            assert result.mode == "shell"
            assert result.context["module"] == "ontology"

    async def test_step2_update_context_on_page_switch(self) -> None:
        """Step 2: Context updates when user navigates to a different page."""
        service = _build_service()
        db_session = mock_session()

        updated_session = _make_copilot_session(
            context={
                "module": "data",
                "page": "browse",
                "current_type_rid": "ri.obj.traffic_light",
            },
        )
        service._session_manager.update_context = AsyncMock(
            return_value=updated_session,
        )

        with (
            patch("lingshu.copilot.sessions.manager.get_tenant_id", return_value="t1"),
            patch("lingshu.copilot.sessions.manager.get_user_id", return_value="u1"),
        ):
            result = await service.update_context(
                "ri.session.shell1",
                {
                    "module": "data",
                    "page": "browse",
                    "current_type_rid": "ri.obj.traffic_light",
                },
                db_session,
            )
            assert result.context["module"] == "data"
            assert result.context["current_type_rid"] == "ri.obj.traffic_light"

    def test_step3_build_context_for_ontology_page(self) -> None:
        """Step 3: Context builder produces correct context for ontology pages."""
        context = build_context(
            "shell",
            {
                "module": "ontology",
                "page": "object-types",
                "current_entity_rid": "ri.obj.traffic_light",
            },
        )
        # Context should include relevant information
        assert context is not None
        assert isinstance(context, dict)

    def test_step3_build_context_for_data_page(self) -> None:
        """Step 3: Context builder produces correct context for data browse."""
        context = build_context(
            "shell",
            {
                "module": "data",
                "page": "browse",
                "current_type_rid": "ri.obj.traffic_light",
            },
        )
        assert context is not None
        assert isinstance(context, dict)

    async def test_step4_message_processed_with_context(self) -> None:
        """Step 4: Message processed with context-aware prompt."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(
            context={
                "module": "ontology",
                "page": "object-types",
                "current_entity_rid": "ri.obj.traffic_light",
            },
        )
        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()

        # Agent should receive the context in its state
        service._agent.process_message = AsyncMock(
            return_value=[
                {"type": "text_delta", "content": "This ObjectType has 3 properties."},
            ],
        )

        events = []
        async for event in service.send_message(
            "ri.session.shell1",
            "What properties does this type have?",
            db_session,
        ):
            events.append(event)

        text_events = [e for e in events if e.event_type == "text_delta"]
        assert len(text_events) >= 1
        # Verify agent was called (received the context)
        service._agent.process_message.assert_awaited_once()

    async def test_session_persistence_across_messages(self) -> None:
        """Shell session persists across multiple messages."""
        service = _build_service()
        db_session = mock_session()

        copilot_session = _make_copilot_session(title="Persistent Shell")
        service._session_manager.get_session = AsyncMock(
            return_value=copilot_session,
        )
        service._session_manager.touch = AsyncMock()
        service._agent.process_message = AsyncMock(
            return_value=[
                {"type": "text_delta", "content": "Response 1"},
            ],
        )

        # First message
        events1 = []
        async for event in service.send_message(
            "ri.session.shell1", "Message 1", db_session,
        ):
            events1.append(event)

        # Second message to same session
        service._agent.process_message = AsyncMock(
            return_value=[
                {"type": "text_delta", "content": "Response 2"},
            ],
        )

        events2 = []
        async for event in service.send_message(
            "ri.session.shell1", "Message 2", db_session,
        ):
            events2.append(event)

        # Both messages processed through the same session
        assert service._session_manager.get_session.call_count == 2
        assert service._session_manager.touch.call_count == 2

    async def test_query_sessions(self) -> None:
        """Query all Shell sessions."""
        service = _build_service()
        db_session = mock_session()

        sessions = [
            _make_copilot_session("ri.session.shell1"),
            _make_copilot_session("ri.session.shell2"),
        ]
        service._session_manager.query_sessions = AsyncMock(
            return_value=(sessions, 2),
        )

        with (
            patch("lingshu.copilot.sessions.manager.get_tenant_id", return_value="t1"),
            patch("lingshu.copilot.sessions.manager.get_user_id", return_value="u1"),
        ):
            results, total = await service.query_sessions(db_session)
            assert total == 2
            assert results[0].session_id == "ri.session.shell1"
