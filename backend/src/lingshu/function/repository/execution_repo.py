"""Execution repository: CRUD for execution records."""

from datetime import datetime
from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.function.models import Execution


class ExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, execution: Execution) -> Execution:
        self._session.add(execution)
        await self._session.flush()
        return execution

    async def get_by_id(
        self, execution_id: str, tenant_id: str,
    ) -> Execution | None:
        result = await self._session.execute(
            select(Execution).where(
                Execution.execution_id == execution_id,
                Execution.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        execution_id: str,
        tenant_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
        confirmed_at: datetime | None = None,
        confirmed_by: str | None = None,
    ) -> Execution | None:
        values: dict[str, Any] = {"status": status}
        if result is not None:
            values["result"] = result
        if completed_at is not None:
            values["completed_at"] = completed_at
        if confirmed_at is not None:
            values["confirmed_at"] = confirmed_at
        if confirmed_by is not None:
            values["confirmed_by"] = confirmed_by

        await self._session.execute(
            update(Execution)
            .where(
                Execution.execution_id == execution_id,
                Execution.tenant_id == tenant_id,
            )
            .values(**values)
        )
        await self._session.flush()
        return await self.get_by_id(execution_id, tenant_id)

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        capability_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Execution], int]:
        base = select(Execution).where(Execution.tenant_id == tenant_id)
        if capability_type:
            base = base.where(Execution.capability_type == capability_type)
        if status:
            base = base.where(Execution.status == status)

        count_result = await self._session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            base.order_by(Execution.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def count_recent(
        self, tenant_id: str, since: datetime,
    ) -> dict[str, int]:
        """Count executions since a timestamp, grouped by status."""
        result = await self._session.execute(
            select(Execution.status, sa_func.count())
            .where(
                Execution.tenant_id == tenant_id,
                Execution.started_at >= since,
            )
            .group_by(Execution.status)
        )
        return {str(row[0]): int(row[1]) for row in result.all()}
