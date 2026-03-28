"""Unit tests for action loader."""

from unittest.mock import AsyncMock, patch

import pytest

from lingshu.function.actions.loader import ActionLoader
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def mock_ontology() -> AsyncMock:
    ontology = AsyncMock()
    ontology.get_object_type = AsyncMock(return_value={
        "api_name": "update_status",
        "display_name": "Update Status",
        "parameters": [
            {"api_name": "robot", "definition_source": "derived_from_object_type_rid"},
            {"api_name": "new_status", "definition_source": "explicit_type"},
        ],
        "execution": {
            "type": "native_crud",
            "native_crud_json": {
                "outputs": [
                    {
                        "name": "robot_update",
                        "target_param": "robot",
                        "operation": "update",
                        "field_mappings": [
                            {"target_field": "status", "source": "new_status"},
                        ],
                        "writeback": True,
                    },
                ],
            },
        },
        "safety_level": "SAFETY_IDEMPOTENT_WRITE",
        "side_effects": [{"category": "DATA_MUTATION"}],
    })
    return ontology


@pytest.fixture
def loader(mock_ontology: AsyncMock) -> ActionLoader:
    return ActionLoader(mock_ontology)


class TestActionLoader:
    @pytest.mark.asyncio
    async def test_load_success(self, loader: ActionLoader) -> None:
        with patch(
            "lingshu.function.actions.loader.get_tenant_id",
            return_value="t1",
        ):
            definition = await loader.load("ri.action.123")
        assert definition.api_name == "update_status"
        assert len(definition.parameters) == 2
        assert len(definition.outputs) == 1
        assert definition.safety_level == "SAFETY_IDEMPOTENT_WRITE"

    @pytest.mark.asyncio
    async def test_load_not_found_raises(
        self, mock_ontology: AsyncMock,
    ) -> None:
        mock_ontology.get_object_type = AsyncMock(return_value=None)
        loader = ActionLoader(mock_ontology)
        with (
            patch(
                "lingshu.function.actions.loader.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await loader.load("ri.action.missing")
        assert exc_info.value.code == ErrorCode.FUNCTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_extract_python_venv_outputs(self, loader: ActionLoader) -> None:
        outputs = loader._extract_outputs({
            "type": "python_venv",
            "python_script": {
                "script": "...",
                "outputs": [{"name": "result"}],
            },
        })
        assert len(outputs) == 1

    @pytest.mark.asyncio
    async def test_extract_unknown_type_empty(self, loader: ActionLoader) -> None:
        outputs = loader._extract_outputs({"type": "unknown"})
        assert outputs == []
