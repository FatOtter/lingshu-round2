"""Skill management: CRUD for copilot_skills table."""

from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.models import CopilotSkill
from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.rid import generate_rid


class SkillManager:
    """CRUD manager for Copilot Skills."""

    async def register(
        self,
        session: AsyncSession,
        *,
        api_name: str,
        display_name: str,
        description: str | None = None,
        system_prompt: str,
        tool_bindings: list[dict[str, Any]] | None = None,
        enabled: bool = True,
    ) -> CopilotSkill:
        """Register a new skill."""
        tenant_id = get_tenant_id()

        skill = CopilotSkill(
            rid=generate_rid("skill"),
            tenant_id=tenant_id,
            api_name=api_name,
            display_name=display_name,
            description=description,
            system_prompt=system_prompt,
            tool_bindings=tool_bindings or [],
            enabled=enabled,
        )
        session.add(skill)
        await session.flush()
        await session.commit()
        return skill

    async def get(
        self, rid: str, session: AsyncSession,
    ) -> CopilotSkill:
        tenant_id = get_tenant_id()
        result = await session.execute(
            select(CopilotSkill).where(
                CopilotSkill.rid == rid,
                CopilotSkill.tenant_id == tenant_id,
            )
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message=f"Skill {rid} not found",
            )
        return skill

    async def update(
        self,
        rid: str,
        updates: dict[str, Any],
        session: AsyncSession,
    ) -> CopilotSkill:
        tenant_id = get_tenant_id()

        await session.execute(
            update(CopilotSkill)
            .where(
                CopilotSkill.rid == rid,
                CopilotSkill.tenant_id == tenant_id,
            )
            .values(**updates)
        )
        await session.flush()
        await session.commit()
        return await self.get(rid, session)

    async def delete(
        self, rid: str, session: AsyncSession,
    ) -> None:
        tenant_id = get_tenant_id()
        result = await session.execute(
            select(CopilotSkill).where(
                CopilotSkill.rid == rid,
                CopilotSkill.tenant_id == tenant_id,
            )
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message=f"Skill {rid} not found",
            )
        await session.delete(skill)
        await session.commit()

    async def query(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CopilotSkill], int]:
        tenant_id = get_tenant_id()
        base = select(CopilotSkill).where(
            CopilotSkill.tenant_id == tenant_id,
        )
        count_result = await session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await session.execute(
            base.order_by(CopilotSkill.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def set_enabled(
        self,
        rid: str,
        enabled: bool,
        session: AsyncSession,
    ) -> CopilotSkill:
        return await self.update(rid, {"enabled": enabled}, session)
