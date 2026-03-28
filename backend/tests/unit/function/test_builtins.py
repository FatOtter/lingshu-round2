"""Unit tests for built-in global functions."""

from unittest.mock import AsyncMock

import pytest

from lingshu.function.globals.builtins import BuiltinFunctions


@pytest.fixture
def mock_ontology() -> AsyncMock:
    ontology = AsyncMock()
    ontology.get_object_type = AsyncMock(return_value={"api_name": "Robot", "rid": "ri.obj.1"})
    ontology.get_link_type = AsyncMock(return_value={"api_name": "Owns", "rid": "ri.link.1"})
    return ontology


@pytest.fixture
def mock_data() -> AsyncMock:
    data = AsyncMock()
    data.query_instances = AsyncMock(return_value={
        "rows": [{"name": "R2-D2"}],
        "total": 1,
        "columns": ["name"],
    })
    data.get_instance = AsyncMock(return_value={"name": "R2-D2", "status": "active"})
    return data


@pytest.fixture
def builtins(mock_ontology: AsyncMock, mock_data: AsyncMock) -> BuiltinFunctions:
    return BuiltinFunctions(mock_ontology, mock_data)


class TestBuiltinFunctions:
    @pytest.mark.asyncio
    async def test_query_instances(
        self, builtins: BuiltinFunctions, mock_data: AsyncMock,
    ) -> None:
        result = await builtins.execute(
            "query_instances",
            {"object_type_rid": "ri.obj.1", "limit": 10},
            "t1",
        )
        assert result["total"] == 1
        mock_data.query_instances.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_instance(
        self, builtins: BuiltinFunctions, mock_data: AsyncMock,
    ) -> None:
        result = await builtins.execute(
            "get_instance",
            {"type_rid": "ri.obj.1", "primary_key": {"id": "1"}},
            "t1",
        )
        assert result["name"] == "R2-D2"

    @pytest.mark.asyncio
    async def test_get_object_type(
        self, builtins: BuiltinFunctions, mock_ontology: AsyncMock,
    ) -> None:
        result = await builtins.execute(
            "get_object_type",
            {"rid": "ri.obj.1"},
            "t1",
        )
        assert result["api_name"] == "Robot"

    @pytest.mark.asyncio
    async def test_get_link_type(
        self, builtins: BuiltinFunctions, mock_ontology: AsyncMock,
    ) -> None:
        result = await builtins.execute(
            "get_link_type",
            {"rid": "ri.link.1"},
            "t1",
        )
        assert result["api_name"] == "Owns"

    @pytest.mark.asyncio
    async def test_unknown_handler(self, builtins: BuiltinFunctions) -> None:
        result = await builtins.execute("nonexistent", {}, "t1")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_query_instances_with_filters(
        self, builtins: BuiltinFunctions, mock_data: AsyncMock,
    ) -> None:
        await builtins.execute(
            "query_instances",
            {
                "object_type_rid": "ri.obj.1",
                "filters": {"status": "active"},
            },
            "t1",
        )
        call_args = mock_data.query_instances.call_args
        filters = call_args[0][2]
        assert len(filters) == 1
        assert filters[0].field == "status"
