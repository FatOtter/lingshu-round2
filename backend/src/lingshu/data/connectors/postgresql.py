"""PostgreSQL Connector: SQL generation, parameterized queries, connection pool."""

import re
import time
from typing import Any

import asyncpg

from lingshu.data.connectors.base import ConnectionTestResult, QueryResult
from lingshu.infra.models import Filter, FilterOperator, SortSpec

# Strict allowlist for SQL identifiers: letters, digits, underscores (1-63 chars)
_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")
_VALID_SORT_ORDER = frozenset({"ASC", "DESC"})


def _validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate a SQL identifier against a strict allowlist pattern."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL {label}: {name!r}")
    return name

# Filter operator to SQL operator mapping
_FILTER_OPS: dict[str, str] = {
    FilterOperator.EQ: "=",
    FilterOperator.NEQ: "!=",
    FilterOperator.GT: ">",
    FilterOperator.GTE: ">=",
    FilterOperator.LT: "<",
    FilterOperator.LTE: "<=",
    FilterOperator.CONTAINS: "LIKE",
}


class PostgreSQLConnector:
    """PostgreSQL data source connector."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._pool: asyncpg.Pool | None = None
        self._schema = config.get("schema", "public")

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self._config["host"],
                port=self._config.get("port", 5432),
                database=self._config["database"],
                user=self._config.get("user", "postgres"),
                password=self._config.get("password", ""),
                min_size=1,
                max_size=5,
            )
        return self._pool

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
        """Execute a parameterized SELECT query."""
        pool = await self._get_pool()

        _validate_identifier(table_path, "table_path")
        for c in columns:
            _validate_identifier(c, "column")
        col_clause = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        table_ref = f'"{self._schema}"."{table_path}"'

        where_parts: list[str] = []
        params: list[Any] = []
        param_idx = 1

        for f in filters:
            op = _FILTER_OPS.get(f.operator, "=")
            if f.operator == FilterOperator.CONTAINS:
                where_parts.append(f'"{f.field}" LIKE ${param_idx}')
                params.append(f"%{f.value}%")
            elif f.operator == FilterOperator.IN:
                where_parts.append(f'"{f.field}" = ANY(${param_idx})')
                params.append(f.value if isinstance(f.value, list) else [f.value])
            else:
                where_parts.append(f'"{f.field}" {op} ${param_idx}')
                params.append(f.value)
            param_idx += 1

        where_clause = " AND ".join(where_parts) if where_parts else "TRUE"

        for s in sort:
            _validate_identifier(s.field, "sort field")
            if s.order.upper() not in _VALID_SORT_ORDER:
                raise ValueError(f"Invalid sort order: {s.order!r}")
        order_parts = [
            f'"{s.field}" {s.order.upper()}' for s in sort
        ]
        order_clause = ", ".join(order_parts) if order_parts else "1"

        # Count query
        count_sql = f"SELECT COUNT(*) FROM {table_ref} WHERE {where_clause}"
        # Data query
        data_sql = (
            f"SELECT {col_clause} FROM {table_ref} "
            f"WHERE {where_clause} "
            f"ORDER BY {order_clause} "
            f"OFFSET ${param_idx} LIMIT ${param_idx + 1}"
        )

        async with pool.acquire() as conn:
            total_row = await conn.fetchval(count_sql, *params)
            total = total_row or 0
            rows = await conn.fetch(data_sql, *params, offset, limit)

        return QueryResult(
            rows=[dict(row) for row in rows],
            total=total,
            columns=columns,
        )

    async def get_row(
        self,
        table_path: str,
        primary_key: dict[str, Any],
        columns: list[str],
    ) -> dict[str, Any] | None:
        """Get a single row by primary key."""
        pool = await self._get_pool()

        _validate_identifier(table_path, "table_path")
        for c in columns:
            _validate_identifier(c, "column")
        col_clause = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        table_ref = f'"{self._schema}"."{table_path}"'

        where_parts: list[str] = []
        params: list[Any] = []
        for idx, (key, value) in enumerate(primary_key.items(), 1):
            _validate_identifier(key, "primary key column")
            where_parts.append(f'"{key}" = ${idx}')
            params.append(value)

        where_clause = " AND ".join(where_parts)
        sql = f"SELECT {col_clause} FROM {table_ref} WHERE {where_clause} LIMIT 1"

        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)

        return dict(row) if row else None

    async def test_connection(self) -> ConnectionTestResult:
        """Test connection by running SELECT 1."""
        start = time.monotonic()
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
            latency = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=True,
                latency_ms=round(latency, 2),
                server_version=str(version) if version else None,
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=False,
                latency_ms=round(latency, 2),
                error=str(e),
            )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
