"""Router integration tests for Data module endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lingshu.data.router import get_db, router, set_data_service
from lingshu.data.schemas.responses import (
    ConnectionResponse,
    ConnectionTestResponse,
    DataOverviewResponse,
)
from lingshu.infra.errors import AppError, ErrorCode, register_exception_handlers
from lingshu.setting.auth.middleware import AuthMiddleware


AUTH_HEADERS = {"X-User-ID": "ri.user.test", "X-Tenant-ID": "ri.tenant.test"}


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    for attr in [
        "create_connection", "query_connections", "get_connection",
        "test_connection", "query_instances", "get_overview",
        "update_connection", "delete_connection",
    ]:
        setattr(svc, attr, AsyncMock())
    set_data_service(svc)
    yield svc
    set_data_service(None)


@pytest.fixture
def client(mock_svc):
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


def _conn_resp(**overrides) -> ConnectionResponse:
    defaults = {
        "rid": "ri.conn.1", "display_name": "Test DB",
        "type": "postgresql", "status": "active",
    }
    defaults.update(overrides)
    return ConnectionResponse(**defaults)


class TestConnectionEndpoints:
    def test_query_connections(self, client, mock_svc):
        mock_svc.query_connections.return_value = ([], 0)

        resp = client.post(
            "/data/v1/connections/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "pagination" in body
        assert body["pagination"]["total"] == 0

    def test_create_connection(self, client, mock_svc):
        mock_svc.create_connection.return_value = _conn_resp()

        resp = client.post(
            "/data/v1/connections",
            json={
                "display_name": "Test DB",
                "type": "postgresql",
                "config": {"host": "localhost", "port": 5432},
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201

    def test_get_connection(self, client, mock_svc):
        mock_svc.get_connection.return_value = _conn_resp()

        resp = client.get("/data/v1/connections/ri.conn.1", headers=AUTH_HEADERS)
        assert resp.status_code == 200

    def test_get_connection_not_found(self, client, mock_svc):
        mock_svc.get_connection.side_effect = AppError(
            code=ErrorCode.DATA_SOURCE_NOT_FOUND,
            message="Connection not found",
        )
        resp = client.get("/data/v1/connections/ri.conn.999", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_test_connection(self, client, mock_svc):
        mock_svc.test_connection.return_value = ConnectionTestResponse(
            success=True, latency_ms=5.0,
        )

        resp = client.post(
            "/data/v1/connections/ri.conn.1/test", headers=AUTH_HEADERS
        )
        assert resp.status_code == 200


class TestInstanceEndpoints:
    def test_query_instances(self, client, mock_svc):
        mock_svc.query_instances.return_value = {
            "rows": [], "columns": [], "total": 0,
        }

        resp = client.post(
            "/data/v1/objects/ri.obj.1/instances/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200


class TestOverview:
    def test_data_overview(self, client, mock_svc):
        mock_svc.get_overview.return_value = {
            "connections": {"total": 3, "active": 2},
        }

        resp = client.get("/data/v1/overview", headers=AUTH_HEADERS)
        assert resp.status_code == 200
