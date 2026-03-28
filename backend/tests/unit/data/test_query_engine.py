"""Unit tests for query engine."""

from unittest.mock import AsyncMock

import pytest

from lingshu.data.connectors.base import QueryResult
from lingshu.data.pipeline.query_engine import QueryEngine
from lingshu.data.pipeline.schema_loader import SchemaInfo
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.models import Filter, FilterOperator, SortSpec


@pytest.fixture
def mock_connector() -> AsyncMock:
    connector = AsyncMock()
    connector.execute_query = AsyncMock(return_value=QueryResult(
        rows=[{"col_name": "Alice", "col_age": 30}],
        total=1,
        columns=["col_name", "col_age"],
    ))
    connector.get_row = AsyncMock(return_value={"col_name": "Alice", "col_age": 30})
    return connector


@pytest.fixture
def schema() -> SchemaInfo:
    return SchemaInfo(
        type_rid="ri.obj.1",
        property_types=[
            {"api_name": "name", "physical_column": "col_name"},
            {"api_name": "age", "physical_column": "col_age"},
            {
                "api_name": "ssn",
                "physical_column": "col_ssn",
                "compliance": {
                    "sensitivity": "CONFIDENTIAL",
                    "masking_strategy": "MASK_REDACT_FULL",
                },
            },
        ],
        asset_mapping={"read_connection_id": "ri.conn.1", "read_asset_path": "users"},
        physical_columns=["col_name", "col_age", "col_ssn"],
        virtual_fields={},
        sortable_fields=["name", "age"],
        filterable_fields=["name", "age"],
        masked_fields={"ssn"},
        primary_key_fields=["name"],
    )


@pytest.fixture
def engine(mock_connector: AsyncMock) -> QueryEngine:
    return QueryEngine(mock_connector)


class TestQueryInstances:
    @pytest.mark.asyncio
    async def test_basic_query(
        self, engine: QueryEngine, schema: SchemaInfo, mock_connector: AsyncMock,
    ) -> None:
        result = await engine.query_instances(schema, "users", [], [])
        assert result.total == 1
        # Should map physical columns back to api_names
        assert "name" in result.rows[0] or "col_name" in result.rows[0]

    @pytest.mark.asyncio
    async def test_filter_on_masked_field_raises(
        self, engine: QueryEngine, schema: SchemaInfo,
    ) -> None:
        filters = [Filter(field="ssn", operator=FilterOperator.EQ, value="123")]
        with pytest.raises(AppError) as exc_info:
            await engine.query_instances(schema, "users", filters, [])
        assert exc_info.value.code == ErrorCode.DATA_MASKED_FIELD_NOT_SORTABLE

    @pytest.mark.asyncio
    async def test_sort_on_masked_field_raises(
        self, engine: QueryEngine, schema: SchemaInfo,
    ) -> None:
        sort = [SortSpec(field="ssn", order="asc")]
        with pytest.raises(AppError) as exc_info:
            await engine.query_instances(schema, "users", [], sort)
        assert exc_info.value.code == ErrorCode.DATA_MASKED_FIELD_NOT_SORTABLE


class TestGetInstance:
    @pytest.mark.asyncio
    async def test_get_by_pk(
        self, engine: QueryEngine, schema: SchemaInfo,
    ) -> None:
        result = await engine.get_instance(schema, "users", {"name": "Alice"})
        assert result is not None
