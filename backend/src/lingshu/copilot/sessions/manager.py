"""Session manager: lifecycle management for copilot sessions."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.models import CopilotSession
from lingshu.copilot.sessions.repository import SessionRepository
from lingshu.infra.context import get_tenant_id, get_user_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.rid import generate_rid


class SessionManager:
    """Manage copilot session lifecycle."""

    async def create_session(
        self,
        session: AsyncSession,
        *,
        mode: str,
        context: dict[str, Any] | None = None,
        model_rid: str | None = None,
    ) -> CopilotSession:
        """Create a new copilot session."""
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        session_id = generate_rid("session")

        copilot_session = CopilotSession(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            mode=mode,
            context=context or {},
            model_rid=model_rid,
            status="active",
        )
        repo = SessionRepository(session)
        created = await repo.create(copilot_session)
        await session.commit()
        return created

    async def get_session(
        self, session_id: str, db_session: AsyncSession,
    ) -> CopilotSession:
        """Get session by ID, raise if not found."""
        tenant_id = get_tenant_id()
        repo = SessionRepository(db_session)
        copilot_session = await repo.get_by_id(session_id, tenant_id)
        if not copilot_session:
            raise AppError(
                code=ErrorCode.COPILOT_SESSION_NOT_FOUND,
                message=f"Session {session_id} not found",
            )
        return copilot_session

    async def update_context(
        self,
        session_id: str,
        context: dict[str, Any],
        db_session: AsyncSession,
    ) -> CopilotSession:
        """Update session context (page switch, no Agent trigger)."""
        tenant_id = get_tenant_id()
        repo = SessionRepository(db_session)
        updated = await repo.update_fields(
            session_id, tenant_id,
            context=context,
            last_active_at=datetime.now(tz=UTC),
        )
        if not updated:
            raise AppError(
                code=ErrorCode.COPILOT_SESSION_NOT_FOUND,
                message=f"Session {session_id} not found",
            )
        await db_session.commit()
        return updated

    async def update_title(
        self,
        session_id: str,
        title: str,
        db_session: AsyncSession,
    ) -> None:
        """Set session title (auto-generated from first message)."""
        tenant_id = get_tenant_id()
        repo = SessionRepository(db_session)
        await repo.update_fields(session_id, tenant_id, title=title)
        await db_session.commit()

    async def touch(
        self, session_id: str, db_session: AsyncSession,
    ) -> None:
        """Update last_active_at timestamp."""
        tenant_id = get_tenant_id()
        repo = SessionRepository(db_session)
        await repo.update_fields(
            session_id, tenant_id,
            last_active_at=datetime.now(tz=UTC),
        )
        await db_session.commit()

    async def delete_session(
        self, session_id: str, db_session: AsyncSession,
    ) -> None:
        """Soft-delete a session."""
        tenant_id = get_tenant_id()
        repo = SessionRepository(db_session)
        deleted = await repo.soft_delete(session_id, tenant_id)
        if not deleted:
            raise AppError(
                code=ErrorCode.COPILOT_SESSION_NOT_FOUND,
                message=f"Session {session_id} not found",
            )
        await db_session.commit()

    async def query_sessions(
        self,
        db_session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CopilotSession], int]:
        """Query sessions for current user."""
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        repo = SessionRepository(db_session)
        return await repo.list_by_user(
            tenant_id, user_id, offset=offset, limit=limit,
        )
