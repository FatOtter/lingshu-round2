"""Query engine: translate api_name queries to physical column queries."""

from typing import Any

from lingshu.data.connectors.base import Connector, QueryResult
from lingshu.data.pipeline.schema_loader import SchemaInfo
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.models import Filter, SortSpec


class QueryEngine:
    """Translates schema-aware queries to connector calls."""

    def __init__(self, connector: Connector) -> None:
        self._connector = connector

    async def query_instances(
        self,
        schema: SchemaInfo,
        table_path: str,
        filters: list[Filter],
        sort: list[SortSpec],
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> QueryResult:
        """Execute a query using schema info for api_name → column mapping."""
        # Build api_name → physical_column mapping
        col_map = self._build_column_map(schema)

        # Validate and translate filters
        translated_filters = self._translate_filters(filters, col_map, schema)

        # Validate and translate sort
        translated_sort = self._translate_sort(sort, col_map, schema)

        # Get physical columns to select
        columns = list(col_map.values())

        result = await self._connector.execute_query(
            table_path, columns, translated_filters, translated_sort,
            offset=offset, limit=limit,
        )

        # Map physical columns back to api_names in results
        reverse_map = {v: k for k, v in col_map.items()}
        mapped_rows = [
            {reverse_map.get(k, k): v for k, v in row.items()}
            for row in result.rows
        ]

        return QueryResult(
            rows=mapped_rows,
            total=result.total,
            columns=list(col_map.keys()),
        )

    async def get_instance(
        self,
        schema: SchemaInfo,
        table_path: str,
        primary_key: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Get a single instance by primary key."""
        col_map = self._build_column_map(schema)

        # Translate primary key from api_name to physical column
        physical_pk: dict[str, Any] = {}
        for api_name, value in primary_key.items():
            physical_col = col_map.get(api_name)
            if physical_col:
                physical_pk[physical_col] = value

        columns = list(col_map.values())
        row = await self._connector.get_row(table_path, physical_pk, columns)
        if not row:
            return None

        # Map back to api_names
        reverse_map = {v: k for k, v in col_map.items()}
        return {reverse_map.get(k, k): v for k, v in row.items()}

    def _build_column_map(self, schema: SchemaInfo) -> dict[str, str]:
        """Build api_name → physical_column mapping."""
        col_map: dict[str, str] = {}
        for pt in schema.property_types:
            api_name = pt.get("api_name", "")
            physical_col = pt.get("physical_column")
            if physical_col:
                col_map[api_name] = physical_col
        return col_map

    def _translate_filters(
        self,
        filters: list[Filter],
        col_map: dict[str, str],
        schema: SchemaInfo,
    ) -> list[Filter]:
        """Translate filter fields from api_name to physical column."""
        translated: list[Filter] = []
        for f in filters:
            if f.field in schema.masked_fields:
                raise AppError(
                    code=ErrorCode.DATA_MASKED_FIELD_NOT_SORTABLE,
                    message=f"Cannot filter on masked field: {f.field}",
                )
            physical_col = col_map.get(f.field)
            if not physical_col:
                # Virtual fields cannot be pushed down
                continue
            translated.append(Filter(
                field=physical_col,
                operator=f.operator,
                value=f.value,
            ))
        return translated

    def _translate_sort(
        self,
        sort: list[SortSpec],
        col_map: dict[str, str],
        schema: SchemaInfo,
    ) -> list[SortSpec]:
        """Translate sort fields from api_name to physical column."""
        translated: list[SortSpec] = []
        for s in sort:
            if s.field in schema.masked_fields:
                raise AppError(
                    code=ErrorCode.DATA_MASKED_FIELD_NOT_SORTABLE,
                    message=f"Cannot sort on masked field: {s.field}",
                )
            physical_col = col_map.get(s.field)
            if physical_col:
                translated.append(SortSpec(field=physical_col, order=s.order))
        return translated
