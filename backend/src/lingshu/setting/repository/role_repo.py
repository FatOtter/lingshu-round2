"""Custom role repository: CRUD operations for custom roles."""

from typing import Any

from sqlalchemy import delete, func as sa_func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.setting.models import CustomRole


class CustomRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, role: CustomRole) -> CustomRole:
        self._session.add(role)
        await self._session.flush()
        return role

    async def get_by_rid(self, rid: str) -> CustomRole | None:
        result = await self._session.execute(
            select(CustomRole).where(CustomRole.rid == rid)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, tenant_id: str, name: str) -> CustomRole | None:
        result = await self._session.execute(
            select(CustomRole).where(
                CustomRole.tenant_id == tenant_id,
                CustomRole.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CustomRole], int]:
        """List custom roles for a tenant with pagination."""
        count_result = await self._session.execute(
            select(sa_func.count())
            .select_from(CustomRole)
            .where(CustomRole.tenant_id == tenant_id)
        )
        total: int = count_result.scalar_one()

        result = await self._session.execute(
            select(CustomRole)
            .where(CustomRole.tenant_id == tenant_id)
            .order_by(CustomRole.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update_fields(self, rid: str, **fields: Any) -> CustomRole | None:
        if not fields:
            return await self.get_by_rid(rid)
        await self._session.execute(
            update(CustomRole).where(CustomRole.rid == rid).values(**fields)
        )
        await self._session.flush()
        return await self.get_by_rid(rid)

    async def delete(self, rid: str) -> None:
        await self._session.execute(
            delete(CustomRole).where(CustomRole.rid == rid)
        )
        await self._session.flush()
