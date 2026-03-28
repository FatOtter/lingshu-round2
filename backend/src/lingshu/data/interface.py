"""DataService Protocol: cross-module contract."""

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.infra.models import Filter, SortSpec


class DataService(Protocol):
    """Protocol for Data module exposed to other modules."""

    async def query_instances(
        self,
        type_rid: str,
        tenant_id: str,
        filters: list[Filter],
        sort: list[SortSpec],
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Query instances of a type. Returns {rows, total, columns, schema}."""
        ...

    async def get_instance(
        self,
        type_rid: str,
        tenant_id: str,
        primary_key: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Get a single instance by primary key."""
        ...

    def invalidate_schema_cache(self, tenant_id: str) -> None:
        """Invalidate cached schemas for a tenant."""
        ...

    async def write_editlog(
        self,
        type_rid: str,
        primary_key: dict[str, Any],
        operation: str,
        field_values: dict[str, Any],
        user_id: str,
        session: AsyncSession,
        *,
        action_type_rid: str | None = None,
        branch: str = "main",
    ) -> str:
        """Write an edit log entry. Returns entry_id."""
        ...
