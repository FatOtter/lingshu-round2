"""Comprehensive integration tests for Function module router endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lingshu.function.router import router, set_function_service, set_workflow_service
from lingshu.function.schemas.responses import (
    CapabilityDescriptor,
    ExecutionDetailResponse,
    ExecutionResponse,
    FunctionOverviewResponse,
    GlobalFunctionResponse,
    WorkflowExecutionResponse,
    WorkflowResponse,
)
from lingshu.infra.errors import register_exception_handlers


# ── Helpers ────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(UTC)


def _exec_resp(**overrides: Any) -> ExecutionResponse:
    defaults = dict(
        execution_id="exec_001", status="completed",
        result={"output": "ok"}, started_at=_now(), completed_at=_now(),
    )
    return ExecutionResponse(**(defaults | overrides))


def _exec_detail(**overrides: Any) -> ExecutionDetailResponse:
    defaults = dict(
        execution_id="exec_001", capability_type="action",
        capability_rid="ri.action.1", status="completed",
        params={}, result={"output": "ok"}, user_id="ri.user.u1",
        started_at=_now(), completed_at=_now(),
    )
    return ExecutionDetailResponse(**(defaults | overrides))


def _func_resp(**overrides: Any) -> GlobalFunctionResponse:
    defaults = dict(
        rid="ri.func.1", api_name="calc_total", display_name="Calculate Total",
        description="Sums values", parameters=[], implementation={"type": "python"},
        version=1, is_active=True, created_at=_now(), updated_at=_now(),
    )
    return GlobalFunctionResponse(**(defaults | overrides))


def _workflow_resp(**overrides: Any) -> WorkflowResponse:
    defaults = dict(
        rid="ri.workflow.1", api_name="wf1", display_name="Workflow 1",
        nodes=[], edges=[], status="draft", version=1, is_active=True,
        created_at=_now(), updated_at=_now(),
    )
    return WorkflowResponse(**(defaults | overrides))


def _cap(**overrides: Any) -> CapabilityDescriptor:
    defaults = dict(
        type="action", rid="ri.action.1", api_name="send_email",
        display_name="Send Email", parameters=[], outputs=[],
    )
    return CapabilityDescriptor(**(defaults | overrides))


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def mock_svc() -> MagicMock:
    svc = MagicMock()
    svc.execute_action = AsyncMock()
    svc.execute_action_batch = AsyncMock()
    svc.execute_action_async = AsyncMock()
    svc._loader = MagicMock()
    svc._loader.load = AsyncMock()
    svc.create_function = AsyncMock()
    svc.query_functions = AsyncMock()
    svc.get_function = AsyncMock()
    svc.update_function = AsyncMock()
    svc.delete_function = AsyncMock()
    svc.execute_function = AsyncMock()
    svc.get_execution = AsyncMock()
    svc.query_executions = AsyncMock()
    svc.confirm_execution = AsyncMock()
    svc.cancel_execution = AsyncMock()
    svc.list_capabilities = AsyncMock()
    svc.get_overview = AsyncMock()
    return svc


@pytest.fixture
def mock_wf_svc() -> MagicMock:
    svc = MagicMock()
    svc.create_workflow = AsyncMock()
    svc.query_workflows = AsyncMock()
    svc.get_workflow = AsyncMock()
    svc.update_workflow = AsyncMock()
    svc.delete_workflow = AsyncMock()
    svc.execute_workflow = AsyncMock()
    return svc


@pytest.fixture
def app(mock_svc: MagicMock, mock_wf_svc: MagicMock) -> FastAPI:
    _app = FastAPI()
    register_exception_handlers(_app)
    _app.include_router(router)
    set_function_service(mock_svc)  # type: ignore[arg-type]
    set_workflow_service(mock_wf_svc)  # type: ignore[arg-type]
    return _app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _override_db(app: FastAPI) -> None:
    from lingshu.function.router import get_db

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db


# ── Action Execution ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_action(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.execute_action.return_value = _exec_resp()
    r = await client.post("/function/v1/actions/ri.action.1/execute", json={
        "params": {"to": "a@b.com"}, "skip_confirmation": True,
    })
    assert r.status_code == 200
    assert r.json()["data"]["execution_id"] == "exec_001"


@pytest.mark.asyncio
async def test_execute_action_batch(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.execute_action_batch.return_value = {
        "total": 2, "succeeded": 2, "failed": 0,
    }
    r = await client.post("/function/v1/actions/ri.action.1/execute/batch", json={
        "batch_params": [{"to": "a@b.com"}, {"to": "c@d.com"}],
    })
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 2


@pytest.mark.asyncio
async def test_execute_action_async(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.execute_action_async.return_value = _exec_resp(status="pending")
    r = await client.post("/function/v1/actions/ri.action.1/execute/async", json={
        "params": {"to": "a@b.com"},
    })
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_action_detail(client: AsyncClient, mock_svc: MagicMock) -> None:
    action_def = MagicMock(
        rid="ri.action.1", api_name="send_email", display_name="Send Email",
        parameters=[], safety_level="SAFETY_READ_ONLY", side_effects=[],
    )
    mock_svc._loader.load.return_value = action_def
    r = await client.get("/function/v1/actions/ri.action.1")
    assert r.status_code == 200
    assert r.json()["data"]["api_name"] == "send_email"


# ── Global Function ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_function(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_function.return_value = _func_resp()
    r = await client.post("/function/v1/functions", json={
        "api_name": "calc_total", "display_name": "Calculate Total",
        "parameters": [], "implementation": {"type": "python"},
    })
    assert r.status_code == 201
    assert r.json()["data"]["rid"] == "ri.func.1"


@pytest.mark.asyncio
async def test_query_functions(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_functions.return_value = ([_func_resp()], 1)
    r = await client.post("/function/v1/functions/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_function(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_function.return_value = _func_resp()
    r = await client.get("/function/v1/functions/ri.func.1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_function(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_function.return_value = _func_resp(display_name="Updated")
    r = await client.put("/function/v1/functions/ri.func.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_function(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/function/v1/functions/ri.func.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Function deleted"


@pytest.mark.asyncio
async def test_execute_function(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.execute_function.return_value = _exec_resp()
    r = await client.post("/function/v1/functions/ri.func.1/execute", json={
        "params": {"x": 1},
    })
    assert r.status_code == 200


# ── Execution Management ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_execution(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_execution.return_value = _exec_detail()
    r = await client.get("/function/v1/executions/exec_001")
    assert r.status_code == 200
    assert r.json()["data"]["execution_id"] == "exec_001"


@pytest.mark.asyncio
async def test_query_executions(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_executions.return_value = ([_exec_detail()], 1)
    r = await client.post("/function/v1/executions/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_query_executions_with_filters(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_executions.return_value = ([], 0)
    r = await client.post("/function/v1/executions/query", json={
        "pagination": {"page": 1, "page_size": 10},
        "capability_type": "action",
        "status": "completed",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_confirm_execution(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.confirm_execution.return_value = _exec_resp(status="completed")
    r = await client.post("/function/v1/executions/exec_001/confirm")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cancel_execution(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.cancel_execution.return_value = _exec_resp(status="cancelled")
    r = await client.post("/function/v1/executions/exec_001/cancel")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "cancelled"


# ── Capability Catalog ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_capabilities(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.list_capabilities.return_value = [_cap()]
    r = await client.post("/function/v1/capabilities/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


@pytest.mark.asyncio
async def test_query_capabilities_with_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.list_capabilities.return_value = []
    r = await client.post("/function/v1/capabilities/query", json={
        "pagination": {"page": 1, "page_size": 20},
        "capability_type": "global_function",
    })
    assert r.status_code == 200


# ── Overview ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_function_overview(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_overview.return_value = FunctionOverviewResponse(
        capabilities={"actions": 5, "functions": 3},
        recent_executions={"total": 10},
    )
    r = await client.get("/function/v1/overview")
    assert r.status_code == 200
    assert r.json()["data"]["capabilities"]["actions"] == 5


# ── Workflow ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_workflow(client: AsyncClient, mock_wf_svc: MagicMock) -> None:
    mock_wf_svc.create_workflow.return_value = _workflow_resp()
    r = await client.post("/function/v1/workflows", json={
        "api_name": "wf1", "display_name": "Workflow 1",
        "nodes": [{"node_id": "n1", "type": "action"}],
        "edges": [{"source_node_id": "n1", "target_node_id": "n2"}],
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_query_workflows(client: AsyncClient, mock_wf_svc: MagicMock) -> None:
    mock_wf_svc.query_workflows.return_value = ([_workflow_resp()], 1)
    r = await client.post("/function/v1/workflows/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_workflow(client: AsyncClient, mock_wf_svc: MagicMock) -> None:
    mock_wf_svc.get_workflow.return_value = _workflow_resp()
    r = await client.get("/function/v1/workflows/ri.workflow.1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_workflow(client: AsyncClient, mock_wf_svc: MagicMock) -> None:
    mock_wf_svc.update_workflow.return_value = _workflow_resp(display_name="Updated")
    r = await client.put("/function/v1/workflows/ri.workflow.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_workflow(client: AsyncClient, mock_wf_svc: MagicMock) -> None:
    r = await client.delete("/function/v1/workflows/ri.workflow.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Workflow deleted"


@pytest.mark.asyncio
async def test_execute_workflow(client: AsyncClient, mock_wf_svc: MagicMock) -> None:
    mock_wf_svc.execute_workflow.return_value = WorkflowExecutionResponse(
        execution_id="wf_exec_1", workflow_rid="ri.workflow.1",
        status="completed", steps=[], outputs={"result": 42},
        started_at=_now(), completed_at=_now(),
    )
    r = await client.post("/function/v1/workflows/ri.workflow.1/execute", json={
        "inputs": {"x": 1},
    })
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "completed"
