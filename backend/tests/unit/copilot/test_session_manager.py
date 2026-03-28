"""Unit tests for session manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.sessions.manager import SessionManager
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


class TestSessionManager:
    @pytest.mark.asyncio
    async def test_create_session(
        self, manager: SessionManager, mock_session: AsyncMock,
    ) -> None:
        with (
            patch(
                "lingshu.copilot.sessions.manager.get_tenant_id",
                return_value="t1",
            ),
            patch(
                "lingshu.copilot.sessions.manager.get_user_id",
                return_value="u1",
            ),
        ):
            result = await manager.create_session(
                mock_session, mode="agent",
            )
        assert result.mode == "agent"
        assert result.session_id.startswith("ri.session.")

    @pytest.mark.asyncio
    async def test_get_session_not_found(
        self, manager: SessionManager, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "lingshu.copilot.sessions.manager.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.get_session("ri.session.missing", mock_session)
        assert exc_info.value.code == ErrorCode.COPILOT_SESSION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_session_not_found(
        self, manager: SessionManager, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "lingshu.copilot.sessions.manager.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.delete_session("ri.session.missing", mock_session)
        assert exc_info.value.code == ErrorCode.COPILOT_SESSION_NOT_FOUND
