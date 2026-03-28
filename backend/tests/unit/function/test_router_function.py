"""Router integration tests for Function module endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lingshu.function.router import get_db, router, set_function_service, set_workflow_service
from lingshu.function.schemas.responses import (
    ExecutionResponse,
    FunctionOverviewResponse,
)
from lingshu.infra.errors import AppError, ErrorCode, register_exception_handlers
from lingshu.setting.auth.middleware import AuthMiddleware


AUTH_HEADERS = {"X-User-ID": "ri.user.test", "X-Tenant-ID": "ri.tenant.test"}


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    for attr in [
        "list_capabilities", "get_overview", "query_functions",
        "execute_action", "get_execution", "query_executions",
        "create_function", "get_function",
    ]:
        setattr(svc, attr, AsyncMock())
    set_function_service(svc)
    yield svc
    set_function_service(None)


@pytest.fixture
def mock_wf_svc():
    svc = MagicMock()
    for attr in [
        "query_workflows", "create_workflow", "get_workflow",
        "execute_workflow",
    ]:
        setattr(svc, attr, AsyncMock())
    set_workflow_service(svc)
    yield svc
    set_workflow_service(None)


@pytest.fixture
def client(mock_svc, mock_wf_svc):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.add_middleware(AuthMiddleware, dev_mode=True)
    app.state.auth_provider = MagicMock()

    mock_session = AsyncMock()

    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestCapabilityEndpoints:
    def test_query_capabilities(self, client, mock_svc):
        mock_svc.list_capabilities.return_value = []

        resp = client.post(
            "/function/v1/capabilities/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []


class TestOverviewEndpoint:
    def test_function_overview(self, client, mock_svc):
        mock_svc.get_overview.return_value = FunctionOverviewResponse(
            capabilities={"action": 5, "function": 3},
            recent_executions={"total": 10},
        )

        resp = client.get("/function/v1/overview", headers=AUTH_HEADERS)
        assert resp.status_code == 200


class TestFunctionEndpoints:
    def test_query_functions(self, client, mock_svc):
        mock_svc.query_functions.return_value = ([], 0)

        resp = client.post(
            "/function/v1/functions/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0


class TestWorkflowEndpoints:
    def test_query_workflows(self, client, mock_wf_svc):
        mock_wf_svc.query_workflows.return_value = ([], 0)

        resp = client.post(
            "/function/v1/workflows/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0


class TestActionEndpoints:
    def test_execute_action(self, client, mock_svc):
        mock_svc.execute_action.return_value = ExecutionResponse(
            execution_id="exec_1", status="completed",
            result={"message": "done"},
        )

        resp = client.post(
            "/function/v1/actions/ri.action.1/execute",
            json={"params": {"key": "value"}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200

    def test_execute_action_not_found(self, client, mock_svc):
        mock_svc.execute_action.side_effect = AppError(
            code=ErrorCode.FUNCTION_NOT_FOUND,
            message="Action not found",
        )
        resp = client.post(
            "/function/v1/actions/ri.action.999/execute",
            json={"params": {}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "FUNCTION_NOT_FOUND"
