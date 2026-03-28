"""Audit log repository: write and read-only query operations."""

from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.setting.models import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: AuditLog) -> AuditLog:
        self._session.add(log)
        await self._session.flush()
        return log

    async def get_by_id(self, log_id: int, tenant_id: str) -> AuditLog | None:
        result = await self._session.execute(
            select(AuditLog).where(
                AuditLog.log_id == log_id,
                AuditLog.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def query(
        self,
        tenant_id: str,
        *,
        module: str | None = None,
        event_type: str | None = None,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_rid: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

        if module is not None:
            stmt = stmt.where(AuditLog.module == module)
        if event_type is not None:
            stmt = stmt.where(AuditLog.event_type == event_type)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if resource_type is not None:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_rid is not None:
            stmt = stmt.where(AuditLog.resource_rid == resource_rid)

        count_result = await self._session.execute(
            select(sa_func.count()).select_from(stmt.subquery())
        )
        total: int = count_result.scalar_one()

        result = await self._session.execute(
            stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def delete_before(self, tenant_id: str, before: datetime) -> int:
        """Delete audit logs created before the given datetime. Returns deleted count."""
        # Count first
        count_result = await self._session.execute(
            select(sa_func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at < before,
            )
        )
        count: int = count_result.scalar_one()

        # Delete
        await self._session.execute(
            sa_delete(AuditLog).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at < before,
            )
        )
        await self._session.flush()
        return count

    async def recent(self, tenant_id: str, limit: int = 10) -> list[AuditLog]:
        result = await self._session.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
