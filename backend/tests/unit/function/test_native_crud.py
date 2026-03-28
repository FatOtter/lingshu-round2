"""Unit tests for NativeCRUD engine."""

from unittest.mock import patch

import pytest

from lingshu.function.actions.engines.native_crud import NativeCRUDEngine


@pytest.fixture
def engine() -> NativeCRUDEngine:
    return NativeCRUDEngine()


class TestNativeCRUDEngine:
    @pytest.mark.asyncio
    async def test_basic_field_mapping(self, engine: NativeCRUDEngine) -> None:
        config = {
            "outputs": [
                {
                    "name": "update_status",
                    "field_mappings": [
                        {"target_field": "status", "source": "new_status"},
                    ],
                },
            ],
        }
        result = await engine.execute(
            config,
            resolved_params={"new_status": "maintenance"},
            instances={},
        )
        assert result.computed_values["update_status"]["status"] == "maintenance"

    @pytest.mark.asyncio
    async def test_nested_source(self, engine: NativeCRUDEngine) -> None:
        config = {
            "outputs": [
                {
                    "name": "copy_owner",
                    "field_mappings": [
                        {"target_field": "last_operator", "source": "robot.owner"},
                    ],
                },
            ],
        }
        result = await engine.execute(
            config,
            resolved_params={"robot": {"primary_key": {"id": "1"}}},
            instances={"robot": {"owner": "Alice", "id": "1"}},
        )
        assert result.computed_values["copy_owner"]["last_operator"] == "Alice"

    @pytest.mark.asyncio
    async def test_builtin_now(self, engine: NativeCRUDEngine) -> None:
        config = {
            "outputs": [
                {
                    "name": "ts_output",
                    "field_mappings": [
                        {"target_field": "updated_at", "value": "$NOW"},
                    ],
                },
            ],
        }
        result = await engine.execute(config, {}, {})
        assert "updated_at" in result.computed_values["ts_output"]

    @pytest.mark.asyncio
    async def test_builtin_user(self, engine: NativeCRUDEngine) -> None:
        config = {
            "outputs": [
                {
                    "name": "user_output",
                    "field_mappings": [
                        {"target_field": "modifier", "value": "$USER"},
                    ],
                },
            ],
        }
        with patch(
            "lingshu.function.actions.engines.native_crud.get_user_id",
            return_value="user_123",
        ):
            result = await engine.execute(config, {}, {})
        assert result.computed_values["user_output"]["modifier"] == "user_123"

    @pytest.mark.asyncio
    async def test_static_value(self, engine: NativeCRUDEngine) -> None:
        config = {
            "outputs": [
                {
                    "name": "static_output",
                    "field_mappings": [
                        {"target_field": "flag", "value": "enabled"},
                    ],
                },
            ],
        }
        result = await engine.execute(config, {}, {})
        assert result.computed_values["static_output"]["flag"] == "enabled"

    @pytest.mark.asyncio
    async def test_multiple_outputs(self, engine: NativeCRUDEngine) -> None:
        config = {
            "outputs": [
                {
                    "name": "out1",
                    "field_mappings": [
                        {"target_field": "a", "source": "x"},
                    ],
                },
                {
                    "name": "out2",
                    "field_mappings": [
                        {"target_field": "b", "source": "y"},
                    ],
                },
            ],
        }
        result = await engine.execute(
            config,
            resolved_params={"x": 1, "y": 2},
            instances={},
        )
        assert result.computed_values["out1"]["a"] == 1
        assert result.computed_values["out2"]["b"] == 2

    @pytest.mark.asyncio
    async def test_empty_outputs(self, engine: NativeCRUDEngine) -> None:
        result = await engine.execute({}, {}, {})
        assert result.computed_values == {}

    @pytest.mark.asyncio
    async def test_data_contains_output_names(
        self, engine: NativeCRUDEngine,
    ) -> None:
        config = {
            "outputs": [
                {"name": "my_output", "field_mappings": []},
            ],
        }
        result = await engine.execute(config, {}, {})
        assert "my_output" in result.data["outputs"]
