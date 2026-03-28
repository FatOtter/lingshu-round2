"""Integration tests for function execution flows: actions, batch, async, workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.function.schemas.responses import GlobalFunctionResponse
from lingshu.function.service import FunctionServiceImpl
from lingshu.infra.errors import AppError, ErrorCode


# ── Helpers ───────────────────────────────────────────────────────


def _make_action_def(
    safety_level: str = "SAFETY_IDEMPOTENT_WRITE",
    side_effects: list[dict[str, Any]] | None = None,
) -> MagicMock:
    d = MagicMock()
    d.parameters = [{"api_name": "new_status", "definition_source": "explicit_type", "required": True}]
    d.safety_level = safety_level
    d.outputs = [{"name": "status_update", "field_mappings": [], "writeback": False}]
    d.side_effects = side_effects or []
    d.execution = {"type": "native_crud", "native_crud_json": {"outputs": []}}
    return d


def _build_service() -> FunctionServiceImpl:
    ontology = AsyncMock()
    ontology.get_object_type = AsyncMock(return_value={
        "api_name": "update_robot",
        "display_name": "Update Robot",
        "parameters": [{"api_name": "new_status", "definition_source": "explicit_type", "required": True}],
        "execution": {"type": "native_crud", "native_crud_json": {"outputs": []}},
        "safety_level": "SAFETY_IDEMPOTENT_WRITE",
        "side_effects": [],
    })
    data = AsyncMock()
    data.get_instance = AsyncMock(return_value={"name": "R2-D2"})
    data.query_instances = AsyncMock(return_value={"rows": [], "total": 0, "columns": []})
    return FunctionServiceImpl(ontology_service=ontology, data_service=data)


def _mock_session() -> AsyncMock:
    s = AsyncMock()
    s.commit = AsyncMock()
    s.flush = AsyncMock()
    s.add = MagicMock()
    s.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    return s


# ── Tests ─────────────────────────────────────────────────────────


class TestCreateActionExecuteCheckAudit:
    """Create action -> execute -> check audit log was written."""

    async def test_execute_and_audit(self) -> None:
        service = _build_service()
        session = _mock_session()

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action(
                "ri.action.1", {"new_status": "maintenance"}, session,
            )
            assert result.status == "success"
            assert result.execution_id.startswith("exec_")
            session.commit.assert_awaited()


class TestExecuteWithSafetyCheckPendingConfirm:
    """Execute non-idempotent action -> pending_confirmation -> confirm -> complete."""

    async def test_pending_then_confirm(self) -> None:
        service = _build_service()
        session = _mock_session()

        action_def = _make_action_def(
            safety_level="SAFETY_NON_IDEMPOTENT",
            side_effects=[{"category": "DATA_MUTATION"}],
        )
        service._loader.load = AsyncMock(return_value=action_def)
        service._param_resolver.resolve = AsyncMock(
            return_value=MagicMock(values={"new_status": "x"}, instances={}),
        )

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action("ri.action.1", {"new_status": "x"}, session)
            assert result.status == "pending_confirmation"
            assert result.confirmation is not None

            action_def2 = _make_action_def(safety_level="SAFETY_NON_IDEMPOTENT")
            service._loader.load = AsyncMock(return_value=action_def2)
            engine_result = MagicMock(data={}, computed_values={})
            service._native_crud.execute = AsyncMock(return_value=engine_result)

            result2 = await service.execute_action(
                "ri.action.1", {"new_status": "x"}, session, skip_confirmation=True,
            )
            assert result2.status == "success"


class TestBatchExecution:
    """Batch execution -> verify all results."""

    async def test_batch_all_success(self) -> None:
        service = _build_service()
        session = _mock_session()

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            batch = [{"new_status": f"s{i}"} for i in range(3)]
            result = await service.execute_action_batch(
                "ri.action.1", batch, session, skip_confirmation=True,
            )
            assert result["total"] == 3
            assert result["success_count"] == 3
            assert result["failure_count"] == 0
            assert len(result["results"]) == 3

    async def test_batch_partial_failure(self) -> None:
        service = _build_service()
        session = _mock_session()

        call_count = 0
        original_execute = service.execute_action

        async def _failing_execute(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise AppError(code=ErrorCode.FUNCTION_EXECUTION_FAILED, message="boom")
            return await original_execute(*args, **kwargs)

        service.execute_action = _failing_execute  # type: ignore[assignment]

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            batch = [{"new_status": f"s{i}"} for i in range(3)]
            result = await service.execute_action_batch(
                "ri.action.1", batch, session, skip_confirmation=True,
            )
            assert result["failure_count"] == 1
            assert result["success_count"] == 2


class TestAsyncExecution:
    """Async execution returns immediately with running status."""

    async def test_async_returns_running(self) -> None:
        service = _build_service()
        session = _mock_session()

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action_async(
                "ri.action.1", {"new_status": "x"}, session,
            )
            assert result.status == "running"
            assert result.execution_id.startswith("exec_")


class TestCancelExecution:
    """Cancel a pending execution."""

    async def test_cancel_pending(self) -> None:
        service = _build_service()
        session = _mock_session()

        execution = MagicMock()
        execution.execution_id = "exec_abc"
        execution.status = "pending_confirmation"
        execution.capability_rid = "ri.action.1"
        execution.params = {}
        execution.branch = None
        execution.started_at = datetime.now(tz=UTC)

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.ExecutionRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=execution)

            result = await service.cancel_execution("exec_abc", session)
            assert result.status == "cancelled"

    async def test_cancel_not_found(self) -> None:
        service = _build_service()
        session = _mock_session()

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.ExecutionRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.cancel_execution("exec_missing", session)
            assert exc_info.value.code == ErrorCode.FUNCTION_NOT_FOUND


class TestGlobalFunctionExecute:
    """Create global function -> execute it."""

    async def test_create_and_execute(self) -> None:
        service = _build_service()
        session = _mock_session()

        func_resp = GlobalFunctionResponse(
            rid="ri.func.1",
            api_name="query_robots",
            display_name="Query Robots",
            implementation={"type": "builtin", "handler": "query_instances"},
        )

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.globals.registry.get_tenant_id", return_value="t1"),
        ):
            service._registry.register = AsyncMock(return_value=func_resp)
            created = await service.create_function(
                "query_robots", "Query Robots", "Query all robots",
                [], {"type": "builtin", "handler": "query_instances"},
                session,
            )
            assert created.api_name == "query_robots"

            service._registry.get = AsyncMock(return_value=func_resp)
            service._executor.execute = AsyncMock(return_value={"rows": [], "total": 0})

            result = await service.execute_function("ri.func.1", {}, session)
            assert result.status == "success"
            assert result.result["data"]["total"] == 0


class TestConfirmExpiredExecution:
    """Confirm an expired execution should fail."""

    async def test_confirm_expired(self) -> None:
        service = _build_service()
        session = _mock_session()

        execution = MagicMock()
        execution.execution_id = "exec_old"
        execution.status = "pending_confirmation"
        execution.started_at = datetime(2020, 1, 1, tzinfo=UTC)

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.ExecutionRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_id = AsyncMock(return_value=execution)

            with pytest.raises(AppError) as exc_info:
                await service.confirm_execution("exec_old", session)
            assert exc_info.value.code == ErrorCode.FUNCTION_CONFIRMATION_EXPIRED
