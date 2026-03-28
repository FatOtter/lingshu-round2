"""Unit tests for Doris connector — SQL generation, filters, connection test."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.data.connectors.base import QueryResult
from lingshu.data.connectors.doris import DorisConnector, _quote
from lingshu.infra.models import Filter, FilterOperator, SortSpec


# ── Helpers ──────────────────────────────────────────────────


def _make_connector(config: dict | None = None) -> DorisConnector:
    return DorisConnector(config or {
        "host": "localhost",
        "port": 9030,
        "database": "test_db",
        "user": "root",
        "password": "",
    })


def _mock_pool() -> MagicMock:
    """Create a mock aiomysql pool with nested cursor context managers."""
    cursor = AsyncMock()
    conn_ctx = AsyncMock()
    conn_ctx.__aenter__ = AsyncMock(return_value=conn_ctx)
    conn_ctx.__aexit__ = AsyncMock(return_value=False)
    conn_ctx.cursor = MagicMock(return_value=cursor)
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=conn_ctx)

    return pool, cursor


# ── Tests ────────────────────────────────────────────────────


class TestQuoteIdentifier:
    def test_simple_name(self) -> None:
        assert _quote("orders") == "`orders`"

    def test_name_with_special_chars(self) -> None:
        assert _quote("my-table") == "`my-table`"


class TestBuildWhere:
    def test_empty_filters(self) -> None:
        connector = _make_connector()
        clause, params = connector._build_where([])
        assert clause == "TRUE"
        assert params == []

    def test_eq_filter(self) -> None:
        connector = _make_connector()
        filters = [Filter(field="status", operator=FilterOperator.EQ, value="active")]
        clause, params = connector._build_where(filters)
        assert "`status` = %s" in clause
        assert params == ["active"]

    def test_contains_filter(self) -> None:
        connector = _make_connector()
        filters = [Filter(field="name", operator=FilterOperator.CONTAINS, value="alice")]
        clause, params = connector._build_where(filters)
        assert "`name` LIKE %s" in clause
        assert params == ["%alice%"]

    def test_in_filter(self) -> None:
        connector = _make_connector()
        filters = [Filter(field="id", operator=FilterOperator.IN, value=[1, 2, 3])]
        clause, params = connector._build_where(filters)
        assert "`id` IN (%s, %s, %s)" in clause
        assert params == [1, 2, 3]

    def test_multiple_filters(self) -> None:
        connector = _make_connector()
        filters = [
            Filter(field="age", operator=FilterOperator.GTE, value=18),
            Filter(field="status", operator=FilterOperator.NEQ, value="banned"),
        ]
        clause, params = connector._build_where(filters)
        assert " AND " in clause
        assert len(params) == 2


class TestExecuteQuery:
    @pytest.mark.asyncio
    async def test_execute_query_builds_correct_sql(self) -> None:
        connector = _make_connector()
        pool, cursor = _mock_pool()
        connector._pool = pool

        cursor.fetchone = AsyncMock(return_value={"COUNT(*)": 42})
        cursor.fetchall = AsyncMock(return_value=[
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ])

        result = await connector.execute_query(
            table_path="users",
            columns=["id", "name"],
            filters=[Filter(field="status", operator=FilterOperator.EQ, value="active")],
            sort=[SortSpec(field="name", order="asc")],
            offset=0,
            limit=10,
        )

        assert isinstance(result, QueryResult)
        assert result.total == 42
        assert len(result.rows) == 2
        assert result.columns == ["id", "name"]

        # Verify SQL was called (count + data)
        assert cursor.execute.call_count == 2


class TestGetRow:
    @pytest.mark.asyncio
    async def test_get_row_found(self) -> None:
        connector = _make_connector()
        pool, cursor = _mock_pool()
        connector._pool = pool

        cursor.fetchone = AsyncMock(return_value={"id": 1, "name": "Alice"})

        row = await connector.get_row(
            table_path="users",
            primary_key={"id": 1},
            columns=["id", "name"],
        )

        assert row == {"id": 1, "name": "Alice"}

    @pytest.mark.asyncio
    async def test_get_row_not_found(self) -> None:
        connector = _make_connector()
        pool, cursor = _mock_pool()
        connector._pool = pool

        cursor.fetchone = AsyncMock(return_value=None)

        row = await connector.get_row(
            table_path="users",
            primary_key={"id": 999},
            columns=["id", "name"],
        )

        assert row is None


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        connector = _make_connector()
        pool, cursor = _mock_pool()
        connector._pool = pool

        cursor.fetchone = AsyncMock(return_value=("5.7.99-Doris-2.1",))

        result = await connector.test_connection()

        assert result.success is True
        assert result.server_version == "5.7.99-Doris-2.1"
        assert result.latency_ms >= 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_failure(self) -> None:
        connector = _make_connector()

        # Make _get_pool raise an error
        async def _fail() -> None:
            msg = "Connection refused"
            raise ConnectionError(msg)

        connector._get_pool = _fail  # type: ignore[assignment]

        result = await connector.test_connection()

        assert result.success is False
        assert "Connection refused" in (result.error or "")
