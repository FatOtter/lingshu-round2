"""Membership repository: user-tenant relationship management."""

from sqlalchemy import delete, func as sa_func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.setting.models import UserTenantMembership


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, membership: UserTenantMembership) -> UserTenantMembership:
        self._session.add(membership)
        await self._session.flush()
        return membership

    async def get(self, user_rid: str, tenant_rid: str) -> UserTenantMembership | None:
        result = await self._session.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_rid == user_rid,
                UserTenantMembership.tenant_rid == tenant_rid,
            )
        )
        return result.scalar_one_or_none()

    async def get_default_tenant(self, user_rid: str) -> UserTenantMembership | None:
        result = await self._session.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_rid == user_rid,
                UserTenantMembership.is_default.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_rid: str) -> list[UserTenantMembership]:
        result = await self._session.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_rid == user_rid,
            )
        )
        return list(result.scalars().all())

    async def list_by_tenant(
        self,
        tenant_rid: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[UserTenantMembership], int]:
        """List memberships for a tenant with pagination."""
        count_result = await self._session.execute(
            select(sa_func.count())
            .select_from(UserTenantMembership)
            .where(UserTenantMembership.tenant_rid == tenant_rid)
        )
        total: int = count_result.scalar_one()
        result = await self._session.execute(
            select(UserTenantMembership)
            .where(UserTenantMembership.tenant_rid == tenant_rid)
            .order_by(UserTenantMembership.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update_role(
        self, user_rid: str, tenant_rid: str, role: str
    ) -> UserTenantMembership | None:
        await self._session.execute(
            update(UserTenantMembership)
            .where(
                UserTenantMembership.user_rid == user_rid,
                UserTenantMembership.tenant_rid == tenant_rid,
            )
            .values(role=role)
        )
        await self._session.flush()
        return await self.get(user_rid, tenant_rid)

    async def delete(self, user_rid: str, tenant_rid: str) -> None:
        await self._session.execute(
            delete(UserTenantMembership).where(
                UserTenantMembership.user_rid == user_rid,
                UserTenantMembership.tenant_rid == tenant_rid,
            )
        )
        await self._session.flush()
