"""BS-03: Action Execution with Safety Confirmation.

Scenario: An operator executes a "restart_device" action which
requires safety confirmation due to high safety_level.

Steps:
1. Load ActionType definition
2. Resolve parameters (explicit + derived)
3. Safety enforcer checks safety_level
4. Execute via NativeCRUD engine
5. Audit log records execution
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.function.schemas.responses import GlobalFunctionResponse
from lingshu.function.service import FunctionServiceImpl
from lingshu.infra.errors import AppError, ErrorCode

from .conftest import mock_session


def _make_action_def(
    safety_level: str = "SAFETY_IDEMPOTENT_WRITE",
    side_effects: list[dict[str, Any]] | None = None,
) -> MagicMock:
    d = MagicMock()
    d.parameters = [
        {"api_name": "device_rid", "definition_source": "explicit_type", "required": True},
        {"api_name": "reason", "definition_source": "explicit_type", "required": True},
    ]
    d.safety_level = safety_level
    d.outputs = [{"name": "restart_result", "field_mappings": [], "writeback": False}]
    d.side_effects = side_effects or []
    d.execution = {"type": "native_crud", "native_crud_json": {"outputs": []}}
    return d


def _build_service() -> FunctionServiceImpl:
    ontology = AsyncMock()
    data = AsyncMock()
    data.get_instance = AsyncMock(return_value={"name": "TL-001"})
    data.query_instances = AsyncMock(return_value={"rows": [], "total": 0, "columns": []})
    return FunctionServiceImpl(ontology_service=ontology, data_service=data)


class TestActionExecution:
    """Complete action execution scenario with safety checks."""

    async def test_step1_execute_idempotent_action_succeeds(self) -> None:
        """Idempotent action executes immediately without confirmation."""
        service = _build_service()
        session = mock_session()

        action_def = _make_action_def(safety_level="SAFETY_IDEMPOTENT_WRITE")
        service._loader.load = AsyncMock(return_value=action_def)
        service._param_resolver.resolve = AsyncMock(
            return_value=MagicMock(
                values={"device_rid": "ri.obj.tl001", "reason": "maintenance"},
                instances={},
            ),
        )
        engine_result = MagicMock(data={"restarted": True}, computed_values={})
        service._native_crud.execute = AsyncMock(return_value=engine_result)

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action(
                "ri.action.restart",
                {"device_rid": "ri.obj.tl001", "reason": "maintenance"},
                session,
            )
            assert result.status == "success"
            assert result.execution_id.startswith("exec_")
            session.commit.assert_awaited()

    async def test_step2_non_idempotent_requires_confirmation(self) -> None:
        """Non-idempotent action requires human confirmation."""
        service = _build_service()
        session = mock_session()

        action_def = _make_action_def(
            safety_level="SAFETY_NON_IDEMPOTENT",
            side_effects=[{"category": "DATA_MUTATION"}],
        )
        service._loader.load = AsyncMock(return_value=action_def)
        service._param_resolver.resolve = AsyncMock(
            return_value=MagicMock(
                values={"device_rid": "ri.obj.tl001", "reason": "critical"},
                instances={},
            ),
        )

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action(
                "ri.action.restart",
                {"device_rid": "ri.obj.tl001", "reason": "critical"},
                session,
            )
            assert result.status == "pending_confirmation"
            assert result.confirmation is not None
            assert "safety_level" in result.confirmation
            assert result.confirmation["safety_level"] == "SAFETY_NON_IDEMPOTENT"

    async def test_step3_confirm_and_execute(self) -> None:
        """After confirmation, action executes successfully."""
        service = _build_service()
        session = mock_session()

        action_def = _make_action_def(safety_level="SAFETY_NON_IDEMPOTENT")
        service._loader.load = AsyncMock(return_value=action_def)
        engine_result = MagicMock(data={"restarted": True}, computed_values={})
        service._native_crud.execute = AsyncMock(return_value=engine_result)

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action(
                "ri.action.restart",
                {"device_rid": "ri.obj.tl001", "reason": "critical"},
                session,
                skip_confirmation=True,
            )
            assert result.status == "success"

    async def test_step4_confirm_expired_execution(self) -> None:
        """Confirming an expired execution raises error."""
        service = _build_service()
        session = mock_session()

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

    async def test_step5_cancel_pending_execution(self) -> None:
        """Cancel a pending execution."""
        service = _build_service()
        session = mock_session()

        execution = MagicMock()
        execution.execution_id = "exec_abc"
        execution.status = "pending_confirmation"
        execution.capability_rid = "ri.action.restart"
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

    async def test_batch_execution(self) -> None:
        """Batch execution processes multiple items."""
        service = _build_service()
        session = mock_session()

        action_def = _make_action_def(safety_level="SAFETY_IDEMPOTENT_WRITE")
        service._loader.load = AsyncMock(return_value=action_def)
        service._param_resolver.resolve = AsyncMock(
            return_value=MagicMock(
                values={"device_rid": "ri.obj.tl001", "reason": "batch restart"},
                instances={},
            ),
        )
        engine_result = MagicMock(data={"restarted": True}, computed_values={})
        service._native_crud.execute = AsyncMock(return_value=engine_result)

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            batch = [
                {"device_rid": f"ri.obj.tl{i:03}", "reason": "batch restart"}
                for i in range(3)
            ]
            result = await service.execute_action_batch(
                "ri.action.restart", batch, session, skip_confirmation=True,
            )
            assert result["total"] == 3
            assert result["success_count"] == 3
            assert result["failure_count"] == 0

    async def test_async_execution_returns_running(self) -> None:
        """Async execution returns immediately with running status."""
        service = _build_service()
        session = mock_session()

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action_async(
                "ri.action.restart",
                {"device_rid": "ri.obj.tl001", "reason": "async test"},
                session,
            )
            assert result.status == "running"
            assert result.execution_id.startswith("exec_")

    async def test_global_function_execute(self) -> None:
        """Create and execute a global function."""
        service = _build_service()
        session = mock_session()

        func_resp = GlobalFunctionResponse(
            rid="ri.func.query_faults",
            api_name="query_faults",
            display_name="Query Faults",
            implementation={"type": "builtin", "handler": "query_instances"},
        )

        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.globals.registry.get_tenant_id", return_value="t1"),
        ):
            service._registry.register = AsyncMock(return_value=func_resp)
            created = await service.create_function(
                "query_faults", "Query Faults", "Query faulty devices",
                [], {"type": "builtin", "handler": "query_instances"}, session,
            )
            assert created.api_name == "query_faults"

            service._registry.get = AsyncMock(return_value=func_resp)
            service._executor.execute = AsyncMock(
                return_value={"rows": [{"id": 1}], "total": 1},
            )

            result = await service.execute_function("ri.func.query_faults", {}, session)
            assert result.status == "success"
