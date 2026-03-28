"""Unit tests for SQLRunner engine."""

import pytest

from lingshu.function.actions.engines.sql_runner import SQLRunnerEngine
from lingshu.infra.errors import AppError


@pytest.fixture
def engine() -> SQLRunnerEngine:
    return SQLRunnerEngine()


class TestSQLRunnerEngine:
    @pytest.mark.asyncio
    async def test_basic_template_rendering(
        self, engine: SQLRunnerEngine,
    ) -> None:
        config = {
            "template": "SELECT * FROM {{robot.table_path}} WHERE id = :robot_id",
            "connection_rid": "ri.connection.test",
        }
        result = await engine.execute(
            config,
            resolved_params={"robot_id": "r123"},
            instances={"robot": {"table_path": "public.robots", "id": "r123"}},
        )
        assert result.data["rendered_sql"] == (
            "SELECT * FROM public.robots WHERE id = :robot_id"
        )
        assert result.data["bind_params"]["robot_id"] == "r123"
        assert result.data["connection_rid"] == "ri.connection.test"

    @pytest.mark.asyncio
    async def test_multiple_brace_placeholders(
        self, engine: SQLRunnerEngine,
    ) -> None:
        config = {
            "template": (
                "SELECT * FROM {{source.table}} "
                "JOIN {{target.table}} ON {{source.table}}.id = {{target.table}}.source_id"
            ),
        }
        result = await engine.execute(
            config,
            resolved_params={},
            instances={
                "source": {"table": "robots"},
                "target": {"table": "tasks"},
            },
        )
        assert "FROM robots" in result.data["rendered_sql"]
        assert "JOIN tasks" in result.data["rendered_sql"]

    @pytest.mark.asyncio
    async def test_bind_params_collected(
        self, engine: SQLRunnerEngine,
    ) -> None:
        config = {
            "template": "UPDATE t SET status = :status WHERE owner = :owner",
        }
        result = await engine.execute(
            config,
            resolved_params={"status": "active", "owner": "alice"},
            instances={},
        )
        assert result.data["bind_params"]["status"] == "active"
        assert result.data["bind_params"]["owner"] == "alice"

    @pytest.mark.asyncio
    async def test_dotted_bind_params(
        self, engine: SQLRunnerEngine,
    ) -> None:
        config = {
            "template": "SELECT * FROM t WHERE name = :robot.name",
        }
        result = await engine.execute(
            config,
            resolved_params={},
            instances={"robot": {"name": "Bot-1"}},
        )
        assert result.data["bind_params"]["robot.name"] == "Bot-1"

    @pytest.mark.asyncio
    async def test_missing_template_raises(
        self, engine: SQLRunnerEngine,
    ) -> None:
        with pytest.raises(AppError, match="requires a 'template'"):
            await engine.execute({}, resolved_params={}, instances={})

    @pytest.mark.asyncio
    async def test_unresolved_brace_kept(
        self, engine: SQLRunnerEngine,
    ) -> None:
        config = {
            "template": "SELECT * FROM {{unknown.table}}",
        }
        result = await engine.execute(config, resolved_params={}, instances={})
        assert "{{unknown.table}}" in result.data["rendered_sql"]

    @pytest.mark.asyncio
    async def test_outputs_populated(
        self, engine: SQLRunnerEngine,
    ) -> None:
        config = {
            "template": "SELECT 1",
            "outputs": [{"name": "query_result"}],
        }
        result = await engine.execute(config, resolved_params={}, instances={})
        assert "query_result" in result.computed_values
        assert "rendered_sql" in result.computed_values["query_result"]

    @pytest.mark.asyncio
    async def test_no_outputs(self, engine: SQLRunnerEngine) -> None:
        config = {"template": "SELECT 1"}
        result = await engine.execute(config, resolved_params={}, instances={})
        assert result.computed_values == {}

    @pytest.mark.asyncio
    async def test_resolved_param_dict_field(
        self, engine: SQLRunnerEngine,
    ) -> None:
        config = {
            "template": "SELECT * FROM {{data.schema}} WHERE x = :data.value",
        }
        result = await engine.execute(
            config,
            resolved_params={"data": {"schema": "my_schema", "value": 42}},
            instances={},
        )
        assert "FROM my_schema" in result.data["rendered_sql"]
        assert result.data["bind_params"]["data.value"] == 42
