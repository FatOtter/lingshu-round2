"""Session repository: CRUD for copilot_sessions table."""

from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.models import CopilotSession


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, copilot_session: CopilotSession) -> CopilotSession:
        self._session.add(copilot_session)
        await self._session.flush()
        return copilot_session

    async def get_by_id(
        self, session_id: str, tenant_id: str,
    ) -> CopilotSession | None:
        result = await self._session.execute(
            select(CopilotSession).where(
                CopilotSession.session_id == session_id,
                CopilotSession.tenant_id == tenant_id,
                CopilotSession.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def update_fields(
        self, session_id: str, tenant_id: str, **fields: Any,
    ) -> CopilotSession | None:
        await self._session.execute(
            update(CopilotSession)
            .where(
                CopilotSession.session_id == session_id,
                CopilotSession.tenant_id == tenant_id,
            )
            .values(**fields)
        )
        await self._session.flush()
        return await self.get_by_id(session_id, tenant_id)

    async def soft_delete(self, session_id: str, tenant_id: str) -> bool:
        result = await self.get_by_id(session_id, tenant_id)
        if not result:
            return False
        await self._session.execute(
            update(CopilotSession)
            .where(
                CopilotSession.session_id == session_id,
                CopilotSession.tenant_id == tenant_id,
            )
            .values(status="deleted")
        )
        await self._session.flush()
        return True

    async def list_by_user(
        self,
        tenant_id: str,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CopilotSession], int]:
        base = select(CopilotSession).where(
            CopilotSession.tenant_id == tenant_id,
            CopilotSession.user_id == user_id,
            CopilotSession.status == "active",
        )
        count_result = await self._session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            base.order_by(CopilotSession.last_active_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total
