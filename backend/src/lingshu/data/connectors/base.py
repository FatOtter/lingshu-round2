"""Connector Protocol: abstract interface for data source access."""

from typing import Any, Protocol

from pydantic import BaseModel, Field

from lingshu.infra.models import Filter, SortSpec


class QueryResult(BaseModel):
    """Standardized query result from any connector."""

    rows: list[dict[str, Any]]
    total: int
    columns: list[str] = Field(default_factory=list)


class ConnectionTestResult(BaseModel):
    """Result of a connection test."""

    success: bool
    latency_ms: float = 0
    server_version: str | None = None
    error: str | None = None


class Connector(Protocol):
    """Protocol for data source connectors."""

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
        """Execute a query against the data source."""
        ...

    async def get_row(
        self,
        table_path: str,
        primary_key: dict[str, Any],
        columns: list[str],
    ) -> dict[str, Any] | None:
        """Get a single row by primary key."""
        ...

    async def test_connection(self) -> ConnectionTestResult:
        """Test the connection to the data source."""
        ...

    async def close(self) -> None:
        """Close the connection."""
        ...
