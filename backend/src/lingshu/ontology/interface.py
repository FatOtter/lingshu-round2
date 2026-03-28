"""OntologyService Protocol: cross-module contract."""

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class OntologyService(Protocol):
    """Protocol for Ontology module exposed to other modules."""

    async def get_object_type(
        self, rid: str, tenant_id: str
    ) -> dict[str, Any] | None:
        """Get Active ObjectType by RID."""
        ...

    async def get_link_type(
        self, rid: str, tenant_id: str
    ) -> dict[str, Any] | None:
        """Get Active LinkType by RID."""
        ...

    async def get_property_types_for_entity(
        self, entity_rid: str, tenant_id: str
    ) -> list[dict[str, Any]]:
        """Get PropertyTypes belonging to an ObjectType or LinkType."""
        ...

    async def get_asset_mapping(
        self, entity_rid: str, tenant_id: str
    ) -> dict[str, Any] | None:
        """Get AssetMapping for an ObjectType or LinkType."""
        ...

    async def query_action_types(
        self, tenant_id: str, *, offset: int = 0, limit: int = 1000
    ) -> tuple[list[dict[str, Any]], int]:
        """Query active ActionType entities for a tenant. Returns (nodes, total)."""
        ...

    async def on_schema_published(
        self, tenant_id: str, snapshot_id: str, session: AsyncSession
    ) -> None:
        """Called after a publish operation, for cache invalidation hooks."""
        ...
