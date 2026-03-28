"""Schema loader: fetch type definitions from OntologyService with caching."""

import time
from typing import Any

from lingshu.ontology.interface import OntologyService

CACHE_TTL_SECONDS = 300  # 5 minutes


class SchemaInfo:
    """Resolved schema information for a type."""

    def __init__(
        self,
        type_rid: str,
        property_types: list[dict[str, Any]],
        asset_mapping: dict[str, Any] | None,
        physical_columns: list[str],
        virtual_fields: dict[str, str],
        sortable_fields: list[str],
        filterable_fields: list[str],
        masked_fields: set[str],
        primary_key_fields: list[str],
    ) -> None:
        self.type_rid = type_rid
        self.property_types = property_types
        self.asset_mapping = asset_mapping
        self.physical_columns = physical_columns
        self.virtual_fields = virtual_fields
        self.sortable_fields = sortable_fields
        self.filterable_fields = filterable_fields
        self.masked_fields = masked_fields
        self.primary_key_fields = primary_key_fields


class _CacheEntry:
    def __init__(self, schema: SchemaInfo, expires_at: float) -> None:
        self.schema = schema
        self.expires_at = expires_at


class SchemaLoader:
    """Loads and caches schema information from OntologyService."""

    def __init__(self, ontology_service: OntologyService) -> None:
        self._ontology = ontology_service
        self._cache: dict[str, _CacheEntry] = {}

    async def get_schema(self, type_rid: str, tenant_id: str) -> SchemaInfo:
        """Get schema for a type, using cache if available."""
        cache_key = f"{tenant_id}:{type_rid}"
        now = time.monotonic()

        entry = self._cache.get(cache_key)
        if entry and entry.expires_at > now:
            return entry.schema

        schema = await self._load_schema(type_rid, tenant_id)
        self._cache[cache_key] = _CacheEntry(
            schema=schema, expires_at=now + CACHE_TTL_SECONDS
        )
        return schema

    async def _load_schema(self, type_rid: str, tenant_id: str) -> SchemaInfo:
        """Load schema from OntologyService."""
        property_types = await self._ontology.get_property_types_for_entity(
            type_rid, tenant_id
        )
        asset_mapping = await self._ontology.get_asset_mapping(type_rid, tenant_id)

        physical_columns: list[str] = []
        virtual_fields: dict[str, str] = {}
        sortable_fields: list[str] = []
        filterable_fields: list[str] = []
        masked_fields: set[str] = set()
        primary_key_fields: list[str] = []

        for pt in property_types:
            api_name = pt.get("api_name", "")
            physical_col = pt.get("physical_column")
            virtual_expr = pt.get("virtual_expression")

            if physical_col:
                physical_columns.append(physical_col)
            elif virtual_expr:
                virtual_fields[api_name] = virtual_expr

            # Check compliance/masking
            compliance = pt.get("compliance")
            is_masked = False
            if compliance:
                sensitivity = compliance.get("sensitivity", "PUBLIC")
                masking = compliance.get("masking_strategy", "MASK_NONE")
                if sensitivity != "PUBLIC" and masking != "MASK_NONE":
                    masked_fields.add(api_name)
                    is_masked = True

            # Masked fields cannot be sorted/filtered
            if not is_masked and physical_col:
                sortable_fields.append(api_name)
                filterable_fields.append(api_name)

        return SchemaInfo(
            type_rid=type_rid,
            property_types=property_types,
            asset_mapping=asset_mapping,
            physical_columns=physical_columns,
            virtual_fields=virtual_fields,
            sortable_fields=sortable_fields,
            filterable_fields=filterable_fields,
            masked_fields=masked_fields,
            primary_key_fields=primary_key_fields,
        )

    def invalidate(self, tenant_id: str) -> None:
        """Invalidate all cached schemas for a tenant."""
        keys_to_remove = [
            k for k in self._cache if k.startswith(f"{tenant_id}:")
        ]
        for k in keys_to_remove:
            del self._cache[k]
