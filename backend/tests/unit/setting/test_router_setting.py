"""Router integration tests for Setting module endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lingshu.infra.errors import AppError, ErrorCode, register_exception_handlers
from lingshu.setting.auth.middleware import AuthMiddleware
from lingshu.setting.router import get_db, router, set_service
from lingshu.setting.schemas.responses import (
    LoginResponse,
    OverviewResponse,
    UserResponse,
)


AUTH_HEADERS = {"X-User-ID": "ri.user.test", "X-Tenant-ID": "ri.tenant.test"}
NOW = datetime.now(timezone.utc)


def _user_resp(**overrides) -> UserResponse:
    defaults = {
        "rid": "ri.user.1", "email": "admin@example.com",
        "display_name": "Admin", "status": "active", "role": "admin",
        "created_at": NOW, "updated_at": NOW,
    }
    defaults.update(overrides)
    return UserResponse(**defaults)


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    for attr in [
        "login", "logout", "get_me", "query_users", "get_user",
        "create_user", "query_tenants", "get_tenant", "query_audit_logs",
        "get_overview", "change_password",
    ]:
        setattr(svc, attr, AsyncMock())
    set_service(svc)
    yield svc
    set_service(None)


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


class TestAuthEndpoints:
    def test_login_success(self, client, mock_svc):
        user = _user_resp()
        login_resp = LoginResponse(user=user)
        mock_svc.login.return_value = (login_resp, "access-token", "refresh-token")
        mock_svc._provider = MagicMock()
        mock_svc._provider._access_ttl = 900
        mock_svc._refresh_ttl = 604800

        resp = client.post(
            "/setting/v1/auth/login",
            json={"email": "admin@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        mock_svc.login.assert_called_once()

    def test_login_invalid_credentials(self, client, mock_svc):
        mock_svc.login.side_effect = AppError(
            code=ErrorCode.SETTING_AUTH_INVALID_CREDENTIALS,
            message="Invalid email or password",
        )
        resp = client.post(
            "/setting/v1/auth/login",
            json={"email": "bad@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "SETTING_AUTH_INVALID_CREDENTIALS"

    def test_logout(self, client, mock_svc):
        resp = client.post("/setting/v1/auth/logout", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["message"] == "Logged out"

    def test_me_returns_user(self, client, mock_svc):
        mock_svc.get_me.return_value = _user_resp()

        resp = client.get("/setting/v1/auth/me", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["email"] == "admin@example.com"


class TestUserEndpoints:
    def test_query_users(self, client, mock_svc):
        mock_svc.query_users.return_value = ([], 0)

        resp = client.post(
            "/setting/v1/users/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "pagination" in body
        assert body["pagination"]["total"] == 0

    def test_get_user(self, client, mock_svc):
        mock_svc.get_user.return_value = _user_resp(rid="ri.user.1")

        resp = client.get("/setting/v1/users/ri.user.1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["rid"] == "ri.user.1"

    def test_get_user_not_found(self, client, mock_svc):
        mock_svc.get_user.side_effect = AppError(
            code=ErrorCode.SETTING_USER_NOT_FOUND,
            message="User not found",
        )
        resp = client.get("/setting/v1/users/ri.user.999", headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestTenantEndpoints:
    def test_query_tenants(self, client, mock_svc):
        mock_svc.query_tenants.return_value = ([], 0)

        resp = client.post(
            "/setting/v1/tenants/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0


class TestAuditEndpoints:
    def test_query_audit_logs(self, client, mock_svc):
        mock_svc.query_audit_logs.return_value = ([], 0)

        resp = client.post(
            "/setting/v1/audit-logs/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0


class TestOverviewEndpoint:
    def test_overview(self, client, mock_svc):
        mock_svc.get_overview.return_value = OverviewResponse(
            users={"total": 5, "active": 4},
            tenants={"total": 2, "active": 2},
            recent_audit=[],
        )

        resp = client.get("/setting/v1/overview", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["users"]["total"] == 5
