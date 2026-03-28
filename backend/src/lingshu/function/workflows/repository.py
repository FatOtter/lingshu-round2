"""Workflow repository: CRUD for workflows table."""

from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.function.models import Workflow
from lingshu.function.workflows.engine import compute_safety_level
from lingshu.function.workflows.models import WorkflowDefinition


class WorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, workflow: Workflow) -> Workflow:
        self._session.add(workflow)
        await self._session.flush()
        return workflow

    async def get_by_rid(
        self, rid: str, tenant_id: str,
    ) -> Workflow | None:
        result = await self._session.execute(
            select(Workflow).where(
                Workflow.rid == rid,
                Workflow.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_fields(
        self, rid: str, tenant_id: str, **fields: Any,
    ) -> Workflow | None:
        await self._session.execute(
            update(Workflow)
            .where(
                Workflow.rid == rid,
                Workflow.tenant_id == tenant_id,
            )
            .values(**fields)
        )
        await self._session.flush()
        return await self.get_by_rid(rid, tenant_id)

    async def delete(self, rid: str, tenant_id: str) -> bool:
        wf = await self.get_by_rid(rid, tenant_id)
        if not wf:
            return False
        await self._session.delete(wf)
        await self._session.flush()
        return True

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        is_active: bool | None = None,
        status: str | None = None,
    ) -> tuple[list[Workflow], int]:
        base = select(Workflow).where(Workflow.tenant_id == tenant_id)
        if is_active is not None:
            base = base.where(Workflow.is_active == is_active)

        count_result = await self._session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            base.order_by(Workflow.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def count_by_tenant(self, tenant_id: str) -> int:
        result = await self._session.execute(
            select(sa_func.count()).where(
                Workflow.tenant_id == tenant_id,
                Workflow.is_active.is_(True),
            )
        )
        return result.scalar_one()


def recompute_safety_level(definition: dict[str, Any]) -> str:
    """Compute the aggregate safety level from a workflow definition dict."""
    parsed = WorkflowDefinition.model_validate(definition)
    # In a full implementation, we'd look up each node's capability safety level.
    # For now, we extract from node input_mappings or default to READ_ONLY.
    levels: list[str] = []
    for node in parsed.nodes:
        level = node.input_mappings.get("safety_level", "SAFETY_READ_ONLY")
        if isinstance(level, str):
            levels.append(level)
    return compute_safety_level(levels)
