"""Unit tests for batch and async execution."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.function.schemas.responses import ExecutionResponse
from lingshu.function.service import FunctionServiceImpl
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def mock_ontology() -> AsyncMock:
    ontology = AsyncMock()
    ontology.get_object_type = AsyncMock(return_value={
        "api_name": "update_robot",
        "display_name": "Update Robot",
        "parameters": [
            {"api_name": "new_status", "definition_source": "explicit_type", "required": True},
        ],
        "execution": {
            "type": "native_crud",
            "native_crud_json": {"outputs": []},
        },
        "safety_level": "SAFETY_IDEMPOTENT_WRITE",
        "side_effects": [],
    })
    return ontology


@pytest.fixture
def mock_data() -> AsyncMock:
    data = AsyncMock()
    data.get_instance = AsyncMock(return_value={"name": "R2-D2"})
    data.query_instances = AsyncMock(return_value={"rows": [], "total": 0, "columns": []})
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


def _context_patches():
    return (
        patch("lingshu.function.service.get_tenant_id", return_value="t1"),
        patch("lingshu.function.service.get_user_id", return_value="u1"),
        patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
        patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
    )


class TestBatchExecution:
    @pytest.mark.asyncio
    async def test_batch_all_success(
        self,
        service: FunctionServiceImpl,
        mock_session: AsyncMock,
    ) -> None:
        batch_params = [
            {"new_status": "active"},
            {"new_status": "maintenance"},
        ]
        with _context_patches()[0], _context_patches()[1], _context_patches()[2], _context_patches()[3]:
            result = await service.execute_action_batch(
                "ri.action.1",
                batch_params,
                mock_session,
                skip_confirmation=True,
            )

        assert result["total"] == 2
        assert result["success_count"] == 2
        assert result["failure_count"] == 0
        assert len(result["results"]) == 2
        for item in result["results"]:
            assert item["status"] == "success"
            assert "execution_id" in item

    @pytest.mark.asyncio
    async def test_batch_mixed_success_failure(
        self,
        service: FunctionServiceImpl,
        mock_session: AsyncMock,
        mock_ontology: AsyncMock,
    ) -> None:
        call_count = 0

        original_get = mock_ontology.get_object_type

        async def alternating_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise AppError(
                    code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                    message="Simulated failure",
                )
            return await original_get(*args, **kwargs)

        mock_ontology.get_object_type = AsyncMock(side_effect=alternating_get)

        batch_params = [
            {"new_status": "active"},
            {"new_status": "broken"},
            {"new_status": "maintenance"},
        ]

        with _context_patches()[0], _context_patches()[1], _context_patches()[2], _context_patches()[3]:
            result = await service.execute_action_batch(
                "ri.action.1",
                batch_params,
                mock_session,
                skip_confirmation=True,
            )

        assert result["total"] == 3
        assert result["success_count"] == 2
        assert result["failure_count"] == 1
        # The second call (index 1) should have failed
        assert result["results"][1]["status"] == "failed"
        assert "error" in result["results"][1]

    @pytest.mark.asyncio
    async def test_batch_empty_params(
        self,
        service: FunctionServiceImpl,
        mock_session: AsyncMock,
    ) -> None:
        with _context_patches()[0], _context_patches()[1], _context_patches()[2], _context_patches()[3]:
            result = await service.execute_action_batch(
                "ri.action.1",
                [],
                mock_session,
            )

        assert result["total"] == 0
        assert result["success_count"] == 0
        assert result["failure_count"] == 0
        assert result["results"] == []


class TestAsyncExecution:
    @pytest.mark.asyncio
    async def test_async_returns_running_immediately(
        self,
        service: FunctionServiceImpl,
        mock_session: AsyncMock,
    ) -> None:
        with (
            _context_patches()[0],
            _context_patches()[1],
            _context_patches()[2],
            _context_patches()[3],
            patch("lingshu.function.service.asyncio") as mock_asyncio,
        ):
            mock_asyncio.create_task = MagicMock()
            result = await service.execute_action_async(
                "ri.action.1",
                {"new_status": "active"},
                mock_session,
            )

        assert result.status == "running"
        assert result.execution_id.startswith("exec_")
        assert result.started_at is not None
        mock_asyncio.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_background_success(
        self,
        service: FunctionServiceImpl,
        mock_session: AsyncMock,
    ) -> None:
        """Test background execution completes and updates status."""

        async def fake_get_session():
            yield mock_session

        mock_execute = AsyncMock(return_value=ExecutionResponse(
            execution_id="exec_inner",
            status="success",
            result={"data": "ok"},
        ))

        with (
            patch.object(service, "execute_action", mock_execute),
            patch(
                "lingshu.infra.database.get_session",
                side_effect=fake_get_session,
            ),
        ):
            await service._execute_async_background(
                "exec_bg_001",
                "ri.action.1",
                {"new_status": "active"},
                tenant_id="t1",
                user_id="u1",
            )

        assert mock_session.commit.called
        mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_background_failure_updates_status(
        self,
        service: FunctionServiceImpl,
        mock_session: AsyncMock,
    ) -> None:
        """Test background execution failure is recorded."""

        async def fake_get_session():
            yield mock_session

        mock_execute = AsyncMock(side_effect=AppError(
            code=ErrorCode.FUNCTION_EXECUTION_FAILED,
            message="Engine failure",
        ))

        with (
            patch.object(service, "execute_action", mock_execute),
            patch(
                "lingshu.infra.database.get_session",
                side_effect=fake_get_session,
            ),
        ):
            # Should not raise - errors are caught internally
            await service._execute_async_background(
                "exec_bg_002",
                "ri.action.1",
                {"new_status": "broken"},
                tenant_id="t1",
                user_id="u1",
            )

        # Session commit should still be called to persist the failed status
        assert mock_session.commit.called
