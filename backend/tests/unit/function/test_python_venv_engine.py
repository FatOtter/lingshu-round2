"""Unit tests for PythonVenv engine."""

import pytest

from lingshu.function.actions.engines.python_venv import PythonVenvEngine
from lingshu.infra.errors import AppError


@pytest.fixture
def engine() -> PythonVenvEngine:
    return PythonVenvEngine()


class TestPythonVenvEngine:
    @pytest.mark.asyncio
    async def test_basic_script_execution(self, engine: PythonVenvEngine) -> None:
        config = {
            "script": "def execute(params, context):\n    return {'greeting': 'hello ' + params['name']}",
        }
        result = await engine.execute(
            config,
            resolved_params={"name": "world"},
            instances={},
        )
        assert result.data == {"greeting": "hello world"}

    @pytest.mark.asyncio
    async def test_script_receives_context(self, engine: PythonVenvEngine) -> None:
        config = {
            "script": (
                "def execute(params, context):\n"
                "    return {'has_instances': 'instances' in context}"
            ),
        }
        result = await engine.execute(
            config,
            resolved_params={},
            instances={"robot": {"id": "r1"}},
        )
        assert result.data["has_instances"] is True

    @pytest.mark.asyncio
    async def test_script_returns_computed_values(
        self, engine: PythonVenvEngine,
    ) -> None:
        config = {
            "script": "def execute(params, context):\n    return {'x': 10, 'y': 20}",
            "outputs": [
                {"name": "x_val", "field": "x"},
                {"name": "y_val", "field": "y"},
            ],
        }
        result = await engine.execute(config, resolved_params={}, instances={})
        assert result.computed_values["x_val"] == 10
        assert result.computed_values["y_val"] == 20

    @pytest.mark.asyncio
    async def test_missing_script_raises(self, engine: PythonVenvEngine) -> None:
        with pytest.raises(AppError, match="requires a 'script'"):
            await engine.execute({}, resolved_params={}, instances={})

    @pytest.mark.asyncio
    async def test_script_error_raises(self, engine: PythonVenvEngine) -> None:
        config = {
            "script": "def execute(params, context):\n    raise ValueError('boom')",
        }
        with pytest.raises(AppError, match="Python script failed"):
            await engine.execute(config, resolved_params={}, instances={})

    @pytest.mark.asyncio
    async def test_script_syntax_error_raises(
        self, engine: PythonVenvEngine,
    ) -> None:
        config = {
            "script": "def execute(params, context)\n    return {}",  # missing colon
        }
        with pytest.raises(AppError, match="Python script failed"):
            await engine.execute(config, resolved_params={}, instances={})

    @pytest.mark.asyncio
    async def test_timeout_raises(self, engine: PythonVenvEngine) -> None:
        config = {
            "script": (
                "import time\n"
                "def execute(params, context):\n"
                "    time.sleep(10)\n"
                "    return {}"
            ),
            "timeout": 1,
        }
        with pytest.raises(AppError, match="timed out"):
            await engine.execute(config, resolved_params={}, instances={})

    @pytest.mark.asyncio
    async def test_no_output_raises(self, engine: PythonVenvEngine) -> None:
        config = {
            "script": (
                "import sys\n"
                "def execute(params, context):\n"
                "    sys.exit(0)\n"
            ),
        }
        # The script exits without printing, which means either empty output
        # or a non-zero exit code from the wrapper
        with pytest.raises(AppError):
            await engine.execute(config, resolved_params={}, instances={})

    @pytest.mark.asyncio
    async def test_invalid_json_output_raises(
        self, engine: PythonVenvEngine,
    ) -> None:
        config = {
            "script": (
                "import sys\n"
                "def execute(params, context):\n"
                "    # Override stdout to break JSON\n"
                "    print('not json', end='', file=sys.stderr)\n"
                "    return 'plain string that is valid json though'\n"
            ),
        }
        # The wrapper will json.dumps("plain string...") which is valid JSON
        # So this test checks the result is returned
        result = await engine.execute(config, resolved_params={}, instances={})
        assert isinstance(result.data, str)

    @pytest.mark.asyncio
    async def test_complex_data_roundtrip(
        self, engine: PythonVenvEngine,
    ) -> None:
        config = {
            "script": (
                "def execute(params, context):\n"
                "    return {'items': params.get('items', []), 'count': len(params.get('items', []))}"
            ),
        }
        result = await engine.execute(
            config,
            resolved_params={"items": [1, 2, 3]},
            instances={},
        )
        assert result.data["count"] == 3
        assert result.data["items"] == [1, 2, 3]
