"""Tenant repository: CRUD operations on the tenants table."""

from datetime import datetime

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.setting.models import Tenant, UserTenantMembership


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tenant: Tenant) -> Tenant:
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def get_by_rid(self, rid: str) -> Tenant | None:
        result = await self._session.execute(select(Tenant).where(Tenant.rid == rid))
        return result.scalar_one_or_none()

    async def list_all(
        self, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[Tenant], int]:
        count_result = await self._session.execute(
            select(sa_func.count()).select_from(Tenant)
        )
        total: int = count_result.scalar_one()
        result = await self._session.execute(
            select(Tenant).order_by(Tenant.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_by_user(
        self, user_rid: str, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[Tenant], int]:
        """List tenants that a user belongs to via membership."""
        base = (
            select(Tenant)
            .join(UserTenantMembership, Tenant.rid == UserTenantMembership.tenant_rid)
            .where(UserTenantMembership.user_rid == user_rid)
        )
        count_result = await self._session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total: int = count_result.scalar_one()
        result = await self._session.execute(
            base.order_by(Tenant.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update_fields(self, rid: str, **fields: object) -> Tenant | None:
        await self._session.execute(
            update(Tenant)
            .where(Tenant.rid == rid)
            .values(**fields, updated_at=datetime.utcnow())
        )
        await self._session.flush()
        return await self.get_by_rid(rid)

    async def count(self) -> int:
        result = await self._session.execute(select(sa_func.count()).select_from(Tenant))
        return result.scalar_one()
