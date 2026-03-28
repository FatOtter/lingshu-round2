"""User repository: CRUD operations on the users table."""

from datetime import datetime

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.setting.models import User, UserTenantMembership


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_rid(self, rid: str) -> User | None:
        result = await self._session.execute(select(User).where(User.rid == rid))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_rid: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        """List users belonging to a tenant via membership."""
        base = (
            select(User)
            .join(UserTenantMembership, User.rid == UserTenantMembership.user_rid)
            .where(UserTenantMembership.tenant_rid == tenant_rid)
        )
        count_result = await self._session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total: int = count_result.scalar_one()
        result = await self._session.execute(
            base.order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update_fields(self, rid: str, **fields: object) -> User | None:
        await self._session.execute(
            update(User)
            .where(User.rid == rid)
            .values(**fields, updated_at=datetime.utcnow())
        )
        await self._session.flush()
        return await self.get_by_rid(rid)

    async def count(self) -> int:
        result = await self._session.execute(select(sa_func.count()).select_from(User))
        return result.scalar_one()

    async def count_by_status(self, tenant_rid: str) -> dict[str, int]:
        result = await self._session.execute(
            select(User.status, sa_func.count())
            .join(UserTenantMembership, User.rid == UserTenantMembership.user_rid)
            .where(UserTenantMembership.tenant_rid == tenant_rid)
            .group_by(User.status)
        )
        return dict(result.all())  # type: ignore[arg-type]
