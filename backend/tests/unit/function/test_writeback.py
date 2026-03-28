"""Unit tests for _process_writeback."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.function.actions.engines.base import EngineResult
from lingshu.function.service import FunctionServiceImpl


@pytest.fixture
def mock_ontology() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_data() -> AsyncMock:
    data = AsyncMock()
    data.write_editlog = AsyncMock(return_value="editlog_001")
    return data


@pytest.fixture
def service(mock_ontology: AsyncMock, mock_data: AsyncMock) -> FunctionServiceImpl:
    return FunctionServiceImpl(
        ontology_service=mock_ontology,
        data_service=mock_data,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    return session


class TestProcessWriteback:
    @pytest.mark.asyncio
    async def test_writeback_true_outputs_written(
        self,
        service: FunctionServiceImpl,
        mock_data: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        outputs_config = [
            {
                "name": "status_update",
                "writeback": True,
                "target_param": "robot",
                "operation": "update",
            },
        ]
        engine_result = EngineResult(
            data={"ok": True},
            computed_values={
                "status_update": {"status": "active"},
            },
        )
        instances = {
            "robot": {
                "_type_rid": "ri.type.robot",
                "_primary_key": {"id": "r1"},
                "name": "R2-D2",
            },
        }

        results = await service._process_writeback(
            outputs_config,
            engine_result,
            {},
            instances,
            mock_session,
            user_id="u1",
            action_type_rid="ri.action.1",
            branch="main",
        )

        assert len(results) == 1
        assert results[0]["output"] == "status_update"
        assert results[0]["entry_id"] == "editlog_001"
        assert results[0]["operation"] == "update"
        assert results[0]["target_param"] == "robot"

        mock_data.write_editlog.assert_called_once_with(
            type_rid="ri.type.robot",
            primary_key={"id": "r1"},
            operation="update",
            field_values={"status": "active"},
            user_id="u1",
            session=mock_session,
            action_type_rid="ri.action.1",
            branch="main",
        )

    @pytest.mark.asyncio
    async def test_writeback_false_outputs_skipped(
        self,
        service: FunctionServiceImpl,
        mock_data: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        outputs_config = [
            {
                "name": "read_only_output",
                "writeback": False,
                "target_param": "robot",
            },
            {
                "name": "no_writeback_field",
                "target_param": "robot",
            },
        ]
        engine_result = EngineResult(data={"ok": True})
        instances = {
            "robot": {
                "_type_rid": "ri.type.robot",
                "_primary_key": {"id": "r1"},
            },
        }

        results = await service._process_writeback(
            outputs_config,
            engine_result,
            {},
            instances,
            mock_session,
            user_id="u1",
            action_type_rid="ri.action.1",
        )

        assert len(results) == 0
        mock_data.write_editlog.assert_not_called()

    @pytest.mark.asyncio
    async def test_writeback_skipped_when_no_write_editlog(
        self,
        mock_ontology: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """When DataService lacks write_editlog, writeback is skipped gracefully."""
        data_no_editlog = AsyncMock(spec=["query_instances", "get_instance"])
        svc = FunctionServiceImpl(
            ontology_service=mock_ontology,
            data_service=data_no_editlog,
        )

        outputs_config = [
            {"name": "out", "writeback": True, "target_param": "robot"},
        ]
        engine_result = EngineResult(
            data={},
            computed_values={"out": {"field": "val"}},
        )
        instances = {
            "robot": {"_type_rid": "t", "_primary_key": {"id": "1"}},
        }

        results = await svc._process_writeback(
            outputs_config,
            engine_result,
            {},
            instances,
            mock_session,
            user_id="u1",
            action_type_rid="ri.action.1",
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_writeback_skips_missing_instance(
        self,
        service: FunctionServiceImpl,
        mock_data: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        outputs_config = [
            {
                "name": "out",
                "writeback": True,
                "target_param": "nonexistent",
                "operation": "update",
            },
        ]
        engine_result = EngineResult(
            data={},
            computed_values={"out": {"field": "val"}},
        )
        instances: dict = {}

        results = await service._process_writeback(
            outputs_config,
            engine_result,
            {},
            instances,
            mock_session,
            user_id="u1",
            action_type_rid="ri.action.1",
        )

        assert len(results) == 0
        mock_data.write_editlog.assert_not_called()
