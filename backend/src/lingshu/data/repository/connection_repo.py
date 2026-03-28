"""Connection repository: CRUD operations on the connections table."""

from datetime import datetime
from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.data.models import Connection


class ConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conn: Connection) -> Connection:
        self._session.add(conn)
        await self._session.flush()
        return conn

    async def get_by_rid(self, rid: str, tenant_id: str) -> Connection | None:
        result = await self._session.execute(
            select(Connection).where(
                Connection.rid == rid,
                Connection.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        conn_type: str | None = None,
    ) -> tuple[list[Connection], int]:
        base = select(Connection).where(Connection.tenant_id == tenant_id)
        if conn_type:
            base = base.where(Connection.type == conn_type)

        count_result = await self._session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total: int = count_result.scalar_one()
        result = await self._session.execute(
            base.order_by(Connection.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update_fields(
        self, rid: str, tenant_id: str, **fields: Any
    ) -> Connection | None:
        await self._session.execute(
            update(Connection)
            .where(Connection.rid == rid, Connection.tenant_id == tenant_id)
            .values(**fields, updated_at=datetime.utcnow())
        )
        await self._session.flush()
        return await self.get_by_rid(rid, tenant_id)

    async def delete(self, rid: str, tenant_id: str) -> bool:
        conn = await self.get_by_rid(rid, tenant_id)
        if not conn:
            return False
        await self._session.delete(conn)
        await self._session.flush()
        return True

    async def count_by_tenant(self, tenant_id: str) -> int:
        result = await self._session.execute(
            select(sa_func.count())
            .select_from(Connection)
            .where(Connection.tenant_id == tenant_id)
        )
        return result.scalar_one()
