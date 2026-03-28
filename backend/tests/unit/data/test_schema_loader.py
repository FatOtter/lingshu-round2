"""Unit tests for schema loader."""

from unittest.mock import AsyncMock

import pytest

from lingshu.data.pipeline.schema_loader import SchemaLoader


@pytest.fixture
def mock_ontology() -> AsyncMock:
    ontology = AsyncMock()
    ontology.get_property_types_for_entity = AsyncMock(return_value=[
        {
            "api_name": "name",
            "physical_column": "col_name",
        },
        {
            "api_name": "email",
            "physical_column": "col_email",
            "compliance": {
                "sensitivity": "CONFIDENTIAL",
                "masking_strategy": "MASK_REDACT_FULL",
            },
        },
        {
            "api_name": "full_name",
            "virtual_expression": "CONCAT(first_name, last_name)",
        },
    ])
    ontology.get_asset_mapping = AsyncMock(return_value={
        "read_connection_id": "ri.conn.test",
        "read_asset_path": "users",
    })
    return ontology


@pytest.fixture
def loader(mock_ontology: AsyncMock) -> SchemaLoader:
    return SchemaLoader(mock_ontology)


class TestSchemaLoader:
    @pytest.mark.asyncio
    async def test_loads_schema(self, loader: SchemaLoader) -> None:
        schema = await loader.get_schema("ri.obj.1", "t1")
        assert schema.type_rid == "ri.obj.1"
        assert "col_name" in schema.physical_columns
        assert "col_email" in schema.physical_columns
        assert "full_name" in schema.virtual_fields

    @pytest.mark.asyncio
    async def test_masked_fields_detected(self, loader: SchemaLoader) -> None:
        schema = await loader.get_schema("ri.obj.1", "t1")
        assert "email" in schema.masked_fields

    @pytest.mark.asyncio
    async def test_masked_fields_not_sortable(self, loader: SchemaLoader) -> None:
        schema = await loader.get_schema("ri.obj.1", "t1")
        assert "email" not in schema.sortable_fields
        assert "name" in schema.sortable_fields

    @pytest.mark.asyncio
    async def test_caching(self, loader: SchemaLoader, mock_ontology: AsyncMock) -> None:
        await loader.get_schema("ri.obj.1", "t1")
        await loader.get_schema("ri.obj.1", "t1")
        # Only called once due to caching
        assert mock_ontology.get_property_types_for_entity.call_count == 1

    @pytest.mark.asyncio
    async def test_invalidation(self, loader: SchemaLoader, mock_ontology: AsyncMock) -> None:
        await loader.get_schema("ri.obj.1", "t1")
        loader.invalidate("t1")
        await loader.get_schema("ri.obj.1", "t1")
        assert mock_ontology.get_property_types_for_entity.call_count == 2

    @pytest.mark.asyncio
    async def test_asset_mapping_loaded(self, loader: SchemaLoader) -> None:
        schema = await loader.get_schema("ri.obj.1", "t1")
        assert schema.asset_mapping is not None
        assert schema.asset_mapping["read_connection_id"] == "ri.conn.test"
