"""Built-in global functions: system functions wrapping Ontology/Data services."""

from typing import Any

from lingshu.data.interface import DataService
from lingshu.infra.models import Filter, FilterOperator
from lingshu.ontology.interface import OntologyService


class BuiltinFunctions:
    """Built-in system functions that delegate to existing services."""

    def __init__(
        self,
        ontology: OntologyService,
        data: DataService,
    ) -> None:
        self._ontology = ontology
        self._data = data

    async def execute(
        self,
        handler: str,
        params: dict[str, Any],
        tenant_id: str,
    ) -> Any:
        """Dispatch to the appropriate built-in function."""
        dispatch: dict[str, Any] = {
            "query_instances": self._query_instances,
            "get_instance": self._get_instance,
            "list_object_types": self._list_object_types,
            "list_link_types": self._list_link_types,
            "get_object_type": self._get_object_type,
            "get_link_type": self._get_link_type,
        }

        func = dispatch.get(handler)
        if func is None:
            return {"error": f"Unknown builtin handler: {handler}"}

        return await func(params, tenant_id)

    async def _query_instances(
        self, params: dict[str, Any], tenant_id: str,
    ) -> Any:
        object_type_rid = params.get("object_type_rid", "")
        raw_filters = params.get("filters", {})
        limit = params.get("limit", 100)
        offset = params.get("offset", 0)

        filters: list[Filter] = []
        if isinstance(raw_filters, dict):
            for field, value in raw_filters.items():
                filters.append(Filter(
                    field=field, operator=FilterOperator.EQ, value=value,
                ))

        return await self._data.query_instances(
            object_type_rid, tenant_id, filters, [],
            offset=offset, limit=limit,
        )

    async def _get_instance(
        self, params: dict[str, Any], tenant_id: str,
    ) -> Any:
        type_rid = params.get("type_rid", "")
        primary_key = params.get("primary_key", {})
        return await self._data.get_instance(type_rid, tenant_id, primary_key)

    async def _list_object_types(
        self, params: dict[str, Any], tenant_id: str,
    ) -> Any:
        # Delegate to ontology service - simplified for P0
        return {"message": "list_object_types not yet fully implemented"}

    async def _list_link_types(
        self, params: dict[str, Any], tenant_id: str,
    ) -> Any:
        return {"message": "list_link_types not yet fully implemented"}

    async def _get_object_type(
        self, params: dict[str, Any], tenant_id: str,
    ) -> Any:
        rid = params.get("rid", "")
        return await self._ontology.get_object_type(rid, tenant_id)

    async def _get_link_type(
        self, params: dict[str, Any], tenant_id: str,
    ) -> Any:
        rid = params.get("rid", "")
        return await self._ontology.get_link_type(rid, tenant_id)
