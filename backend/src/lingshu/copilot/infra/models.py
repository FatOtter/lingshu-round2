"""Base model management: CRUD for copilot_models table."""

from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.models import CopilotModel
from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.rid import generate_rid


class ModelManager:
    """Manage base model configurations."""

    async def register(
        self,
        session: AsyncSession,
        *,
        api_name: str,
        display_name: str,
        provider: str,
        connection: dict[str, Any],
        parameters: dict[str, Any] | None = None,
        is_default: bool = False,
    ) -> CopilotModel:
        """Register a new base model."""
        tenant_id = get_tenant_id()

        # If setting as default, clear existing defaults
        if is_default:
            await session.execute(
                update(CopilotModel)
                .where(
                    CopilotModel.tenant_id == tenant_id,
                    CopilotModel.is_default.is_(True),
                )
                .values(is_default=False)
            )

        model = CopilotModel(
            rid=generate_rid("model"),
            tenant_id=tenant_id,
            api_name=api_name,
            display_name=display_name,
            provider=provider,
            connection=connection,
            parameters=parameters or {},
            is_default=is_default,
        )
        session.add(model)
        await session.flush()
        await session.commit()
        return model

    async def get(
        self, rid: str, session: AsyncSession,
    ) -> CopilotModel:
        tenant_id = get_tenant_id()
        result = await session.execute(
            select(CopilotModel).where(
                CopilotModel.rid == rid,
                CopilotModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message=f"Model {rid} not found",
            )
        return model

    async def update(
        self,
        rid: str,
        updates: dict[str, Any],
        session: AsyncSession,
    ) -> CopilotModel:
        tenant_id = get_tenant_id()

        # Handle is_default
        if updates.get("is_default"):
            await session.execute(
                update(CopilotModel)
                .where(
                    CopilotModel.tenant_id == tenant_id,
                    CopilotModel.is_default.is_(True),
                )
                .values(is_default=False)
            )

        await session.execute(
            update(CopilotModel)
            .where(
                CopilotModel.rid == rid,
                CopilotModel.tenant_id == tenant_id,
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
            select(CopilotModel).where(
                CopilotModel.rid == rid,
                CopilotModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message=f"Model {rid} not found",
            )
        await session.delete(model)
        await session.commit()

    async def query(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CopilotModel], int]:
        tenant_id = get_tenant_id()
        base = select(CopilotModel).where(
            CopilotModel.tenant_id == tenant_id,
        )
        count_result = await session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await session.execute(
            base.order_by(CopilotModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_default(
        self, session: AsyncSession,
    ) -> CopilotModel | None:
        tenant_id = get_tenant_id()
        result = await session.execute(
            select(CopilotModel).where(
                CopilotModel.tenant_id == tenant_id,
                CopilotModel.is_default.is_(True),
            )
        )
        return result.scalar_one_or_none()
