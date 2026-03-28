"""Iceberg Connector: PyIceberg + Nessie Catalog for lakehouse data access."""

import time
from typing import Any

from lingshu.data.connectors.base import ConnectionTestResult, QueryResult
from lingshu.infra.models import Filter, FilterOperator, SortSpec


class IcebergConnector:
    """Iceberg data source connector via PyIceberg with Nessie REST Catalog."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._catalog: Any = None
        self._warehouse = config.get("warehouse", "s3://warehouse")
        self._nessie_url = config.get("nessie_url", "http://localhost:19120/api/v2")
        self._s3_endpoint = config.get("s3_endpoint", "http://localhost:9000")
        self._branch = config.get("branch", "main")

    def _get_catalog(self) -> Any:
        """Lazy-load PyIceberg catalog with Nessie REST backend."""
        if self._catalog is None:
            from pyiceberg.catalog.rest import RestCatalog

            self._catalog = RestCatalog(
                name="nessie",
                **{
                    "uri": self._nessie_url,
                    "warehouse": self._warehouse,
                    "s3.endpoint": self._s3_endpoint,
                    "s3.access-key-id": self._config["s3_access_key"],
                    "s3.secret-access-key": self._config["s3_secret_key"],
                    "ref": self._branch,
                },
            )
        return self._catalog

    async def execute_query(
        self,
        table_path: str,
        columns: list[str],
        filters: list[Filter],
        sort: list[SortSpec],
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> QueryResult:
        """Execute a scan on an Iceberg table."""
        import asyncio

        return await asyncio.to_thread(
            self._execute_query_sync,
            table_path, columns, filters, sort,
            offset=offset, limit=limit,
        )

    def _execute_query_sync(
        self,
        table_path: str,
        columns: list[str],
        filters: list[Filter],
        sort: list[SortSpec],
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> QueryResult:
        """Synchronous query execution via PyIceberg table scan."""
        catalog = self._get_catalog()
        table = catalog.load_table(table_path)

        # Build row filter expression
        row_filter = self._build_filter(filters)
        selected = tuple(columns) if columns else ()

        scan_kwargs: dict[str, Any] = {}
        if row_filter:
            scan_kwargs["row_filter"] = row_filter
        if selected:
            scan_kwargs["selected_fields"] = selected

        scan = table.scan(**scan_kwargs)
        arrow_table = scan.to_arrow()

        total = arrow_table.num_rows

        # Apply sorting via Arrow compute
        if sort:
            import pyarrow.compute as pc

            sort_keys = [
                (s.field, "ascending" if s.order.lower() == "asc" else "descending")
                for s in sort
            ]
            indices = pc.sort_indices(arrow_table, sort_keys=sort_keys)
            arrow_table = arrow_table.take(indices)

        # Apply pagination
        arrow_table = arrow_table.slice(offset, limit)

        rows = arrow_table.to_pylist()
        result_columns = columns if columns else [c.name for c in arrow_table.schema]

        return QueryResult(rows=rows, total=total, columns=result_columns)

    @staticmethod
    def _build_filter(filters: list[Filter]) -> str:
        """Convert Filter list to an Iceberg expression string."""
        parts: list[str] = []
        for f in filters:
            field = f.field
            value = f.value
            quoted = f"'{value}'" if isinstance(value, str) else str(value)

            if f.operator == FilterOperator.EQ:
                parts.append(f"{field} == {quoted}")
            elif f.operator == FilterOperator.NEQ:
                parts.append(f"{field} != {quoted}")
            elif f.operator == FilterOperator.GT:
                parts.append(f"{field} > {quoted}")
            elif f.operator == FilterOperator.GTE:
                parts.append(f"{field} >= {quoted}")
            elif f.operator == FilterOperator.LT:
                parts.append(f"{field} < {quoted}")
            elif f.operator == FilterOperator.LTE:
                parts.append(f"{field} <= {quoted}")
            elif f.operator == FilterOperator.CONTAINS:
                # Iceberg doesn't support LIKE; use starts_with as approximation
                parts.append(f"{field} >= '{value}'")

        return " AND ".join(parts) if parts else ""

    async def get_row(
        self,
        table_path: str,
        primary_key: dict[str, Any],
        columns: list[str],
    ) -> dict[str, Any] | None:
        """Get a single row by primary key via scan + filter."""
        pk_filters = [
            Filter(field=k, operator=FilterOperator.EQ, value=v)
            for k, v in primary_key.items()
        ]
        result = await self.execute_query(
            table_path, columns, pk_filters, [], offset=0, limit=1,
        )
        return result.rows[0] if result.rows else None

    async def test_connection(self) -> ConnectionTestResult:
        """Test connection by listing namespaces."""
        start = time.monotonic()
        try:
            import asyncio

            catalog = await asyncio.to_thread(self._get_catalog)
            namespaces = await asyncio.to_thread(catalog.list_namespaces)
            latency = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=True,
                latency_ms=round(latency, 2),
                server_version=f"Nessie Catalog ({len(namespaces)} namespaces)",
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=False,
                latency_ms=round(latency, 2),
                error=str(e),
            )

    async def close(self) -> None:
        """No persistent connection to close."""
        self._catalog = None
