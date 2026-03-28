"""Global Function repository: CRUD for global_functions table."""

from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.function.models import GlobalFunction


class GlobalFunctionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, func: GlobalFunction) -> GlobalFunction:
        self._session.add(func)
        await self._session.flush()
        return func

    async def get_by_rid(
        self, rid: str, tenant_id: str,
    ) -> GlobalFunction | None:
        result = await self._session.execute(
            select(GlobalFunction).where(
                GlobalFunction.rid == rid,
                GlobalFunction.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_api_name(
        self, api_name: str, tenant_id: str,
    ) -> GlobalFunction | None:
        result = await self._session.execute(
            select(GlobalFunction).where(
                GlobalFunction.api_name == api_name,
                GlobalFunction.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_fields(
        self, rid: str, tenant_id: str, **fields: Any,
    ) -> GlobalFunction | None:
        await self._session.execute(
            update(GlobalFunction)
            .where(
                GlobalFunction.rid == rid,
                GlobalFunction.tenant_id == tenant_id,
            )
            .values(**fields)
        )
        await self._session.flush()
        return await self.get_by_rid(rid, tenant_id)

    async def delete(self, rid: str, tenant_id: str) -> bool:
        func = await self.get_by_rid(rid, tenant_id)
        if not func:
            return False
        await self._session.delete(func)
        await self._session.flush()
        return True

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> tuple[list[GlobalFunction], int]:
        base = select(GlobalFunction).where(
            GlobalFunction.tenant_id == tenant_id
        )
        if is_active is not None:
            base = base.where(GlobalFunction.is_active == is_active)

        count_result = await self._session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await self._session.execute(
            base.order_by(GlobalFunction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def count_by_tenant(self, tenant_id: str) -> int:
        result = await self._session.execute(
            select(sa_func.count()).where(
                GlobalFunction.tenant_id == tenant_id,
                GlobalFunction.is_active.is_(True),
            )
        )
        return result.scalar_one()
