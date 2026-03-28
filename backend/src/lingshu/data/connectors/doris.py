"""Doris Connector: MySQL-protocol async access to Apache Doris OLAP engine."""

import re
import time
from typing import Any

import aiomysql

from lingshu.data.connectors.base import ConnectionTestResult, QueryResult
from lingshu.infra.models import Filter, FilterOperator, SortSpec

# Strict allowlist for SQL identifiers
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


def _quote(name: str) -> str:
    """Quote an identifier with backticks (Doris/MySQL style)."""
    return f"`{name}`"


class DorisConnector:
    """Apache Doris data source connector (MySQL protocol via aiomysql)."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._pool: aiomysql.Pool | None = None

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                host=self._config["host"],
                port=self._config.get("port", 9030),
                db=self._config.get("database", ""),
                user=self._config.get("user", "root"),
                password=self._config.get("password", ""),
                minsize=1,
                maxsize=5,
                autocommit=True,
            )
        return self._pool

    def _build_where(
        self, filters: list[Filter],
    ) -> tuple[str, list[Any]]:
        """Build WHERE clause and parameter list from filters."""
        where_parts: list[str] = []
        params: list[Any] = []

        for f in filters:
            op = _FILTER_OPS.get(f.operator, "=")
            if f.operator == FilterOperator.CONTAINS:
                where_parts.append(f"{_quote(f.field)} LIKE %s")
                params.append(f"%{f.value}%")
            elif f.operator == FilterOperator.IN:
                values = f.value if isinstance(f.value, list) else [f.value]
                placeholders = ", ".join(["%s"] * len(values))
                where_parts.append(f"{_quote(f.field)} IN ({placeholders})")
                params.extend(values)
            else:
                where_parts.append(f"{_quote(f.field)} {op} %s")
                params.append(f.value)

        where_clause = " AND ".join(where_parts) if where_parts else "TRUE"
        return where_clause, params

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
        """Execute a parameterized SELECT query against Doris."""
        pool = await self._get_pool()

        _validate_identifier(table_path, "table_path")
        for c in columns:
            _validate_identifier(c, "column")
        col_clause = ", ".join(_quote(c) for c in columns) if columns else "*"
        table_ref = _quote(table_path)

        where_clause, params = self._build_where(filters)

        for s in sort:
            _validate_identifier(s.field, "sort field")
            if s.order.upper() not in _VALID_SORT_ORDER:
                raise ValueError(f"Invalid sort order: {s.order!r}")
        order_parts = [
            f"{_quote(s.field)} {s.order.upper()}" for s in sort
        ]
        order_clause = ", ".join(order_parts) if order_parts else "1"

        count_sql = f"SELECT COUNT(*) FROM {table_ref} WHERE {where_clause}"
        data_sql = (
            f"SELECT {col_clause} FROM {table_ref} "
            f"WHERE {where_clause} "
            f"ORDER BY {order_clause} "
            f"LIMIT %s OFFSET %s"
        )

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(count_sql, params)
                count_row = await cur.fetchone()
                total = count_row["COUNT(*)"] if count_row else 0

                await cur.execute(data_sql, [*params, limit, offset])
                rows = await cur.fetchall()

        return QueryResult(
            rows=[dict(r) for r in rows],
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
        col_clause = ", ".join(_quote(c) for c in columns) if columns else "*"
        table_ref = _quote(table_path)

        where_parts: list[str] = []
        params: list[Any] = []
        for key, value in primary_key.items():
            _validate_identifier(key, "primary key column")
            where_parts.append(f"{_quote(key)} = %s")
            params.append(value)

        where_clause = " AND ".join(where_parts)
        sql = f"SELECT {col_clause} FROM {table_ref} WHERE {where_clause} LIMIT 1"

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()

        return dict(row) if row else None

    async def test_connection(self) -> ConnectionTestResult:
        """Test connection by running SELECT 1."""
        start = time.monotonic()
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT VERSION()")
                    result = await cur.fetchone()
                    version = result[0] if result else None
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
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
