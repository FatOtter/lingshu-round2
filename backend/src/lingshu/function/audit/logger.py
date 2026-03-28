"""Audit logger: persist execution records."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.function.models import Execution
from lingshu.function.repository.execution_repo import ExecutionRepository


class AuditLogger:
    """Log execution events to the executions table."""

    async def log_start(
        self,
        session: AsyncSession,
        *,
        execution_id: str,
        tenant_id: str,
        capability_type: str,
        capability_rid: str,
        status: str,
        params: dict[str, Any],
        safety_level: str | None,
        side_effects: list[dict[str, Any]],
        user_id: str,
        branch: str | None = None,
    ) -> Execution:
        """Create execution record at start of execution."""
        execution = Execution(
            execution_id=execution_id,
            tenant_id=tenant_id,
            capability_type=capability_type,
            capability_rid=capability_rid,
            status=status,
            params=params,
            safety_level=safety_level,
            side_effects=side_effects,
            user_id=user_id,
            branch=branch,
        )
        repo = ExecutionRepository(session)
        return await repo.create(execution)

    async def log_complete(
        self,
        session: AsyncSession,
        *,
        execution_id: str,
        tenant_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        confirmed_by: str | None = None,
    ) -> Execution | None:
        """Update execution record on completion."""
        repo = ExecutionRepository(session)
        return await repo.update_status(
            execution_id,
            tenant_id,
            status=status,
            result=result,
            completed_at=datetime.now(tz=UTC),
            confirmed_by=confirmed_by,
        )
