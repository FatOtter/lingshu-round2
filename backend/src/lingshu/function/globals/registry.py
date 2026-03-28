"""Global Function registry: CRUD + version management."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.function.models import GlobalFunction
from lingshu.function.repository.function_repo import GlobalFunctionRepository
from lingshu.function.schemas.responses import GlobalFunctionResponse
from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.rid import generate_rid


class FunctionRegistry:
    """Manage Global Function lifecycle."""

    async def register(
        self,
        session: AsyncSession,
        *,
        api_name: str,
        display_name: str,
        description: str | None,
        parameters: list[dict[str, Any]],
        implementation: dict[str, Any],
    ) -> GlobalFunctionResponse:
        """Register a new global function."""
        tenant_id = get_tenant_id()
        repo = GlobalFunctionRepository(session)

        # Check uniqueness
        existing = await repo.get_by_api_name(api_name, tenant_id)
        if existing:
            raise AppError(
                code=ErrorCode.COMMON_CONFLICT,
                message=f"Function with api_name '{api_name}' already exists",
            )

        func = GlobalFunction(
            rid=generate_rid("func"),
            tenant_id=tenant_id,
            api_name=api_name,
            display_name=display_name,
            description=description,
            parameters=parameters,
            implementation=implementation,
            version=1,
            is_active=True,
        )
        created = await repo.create(func)
        await session.commit()
        return self._to_response(created)

    async def get(
        self, rid: str, session: AsyncSession,
    ) -> GlobalFunctionResponse:
        tenant_id = get_tenant_id()
        repo = GlobalFunctionRepository(session)
        func = await repo.get_by_rid(rid, tenant_id)
        if not func:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Function {rid} not found",
            )
        return self._to_response(func)

    async def update(
        self,
        rid: str,
        updates: dict[str, Any],
        session: AsyncSession,
    ) -> GlobalFunctionResponse:
        tenant_id = get_tenant_id()
        repo = GlobalFunctionRepository(session)

        existing = await repo.get_by_rid(rid, tenant_id)
        if not existing:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Function {rid} not found",
            )

        # Auto-increment version
        updates["version"] = existing.version + 1
        func = await repo.update_fields(rid, tenant_id, **updates)
        await session.commit()
        return self._to_response(func) if func else self._to_response(existing)

    async def delete(
        self, rid: str, session: AsyncSession,
    ) -> None:
        tenant_id = get_tenant_id()
        repo = GlobalFunctionRepository(session)
        deleted = await repo.delete(rid, tenant_id)
        if not deleted:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Function {rid} not found",
            )
        await session.commit()

    async def query(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[GlobalFunctionResponse], int]:
        tenant_id = get_tenant_id()
        repo = GlobalFunctionRepository(session)
        funcs, total = await repo.list_by_tenant(
            tenant_id, offset=offset, limit=limit, is_active=True,
        )
        return [self._to_response(f) for f in funcs], total

    def _to_response(self, func: GlobalFunction) -> GlobalFunctionResponse:
        return GlobalFunctionResponse(
            rid=func.rid,
            api_name=func.api_name,
            display_name=func.display_name,
            description=func.description,
            parameters=func.parameters,
            implementation=func.implementation,
            version=func.version,
            is_active=func.is_active,
            created_at=func.created_at,
            updated_at=func.updated_at,
        )
