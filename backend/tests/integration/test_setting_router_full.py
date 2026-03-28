"""Comprehensive integration tests for Setting module router endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lingshu.infra.errors import register_exception_handlers
from lingshu.setting.router import router, set_service
from lingshu.setting.schemas.responses import (
    AuditLogResponse,
    LoginResponse,
    MemberResponse,
    OverviewResponse,
    RoleResponse,
    SsoConfigResponse,
    TenantResponse,
    UserResponse,
)


# ── Helpers ────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(UTC)


def _user_resp(**overrides: Any) -> UserResponse:
    defaults = dict(
        rid="ri.user.u1", email="user@example.com", display_name="Test User",
        status="active", role="admin", tenant=None, created_at=_now(), updated_at=_now(),
    )
    return UserResponse(**(defaults | overrides))


def _tenant_resp(**overrides: Any) -> TenantResponse:
    defaults = dict(
        rid="ri.tenant.t1", display_name="Default", status="active",
        config=None, created_at=_now(), updated_at=_now(),
    )
    return TenantResponse(**(defaults | overrides))


def _member_resp(**overrides: Any) -> MemberResponse:
    defaults = dict(
        user_rid="ri.user.u1", display_name="Test User",
        email="user@example.com", role="admin", is_default=True, created_at=_now(),
    )
    return MemberResponse(**(defaults | overrides))


def _role_resp(**overrides: Any) -> RoleResponse:
    defaults = dict(
        rid="ri.role.r1", name="admin", description="Admin role",
        permissions=[{"resource_type": "*", "action": "*"}],
        is_system=True, created_at=_now(), updated_at=_now(),
    )
    return RoleResponse(**(defaults | overrides))


def _audit_resp(**overrides: Any) -> AuditLogResponse:
    defaults = dict(
        log_id=1, module="setting", event_type="user.created",
        resource_type="user", resource_rid="ri.user.u1", user_id="ri.user.u1",
        action="create", details=None, request_id="req_1", created_at=_now(),
    )
    return AuditLogResponse(**(defaults | overrides))


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def mock_service() -> MagicMock:
    svc = MagicMock()
    # Auth
    svc.login = AsyncMock()
    svc.logout = AsyncMock()
    svc.refresh = AsyncMock()
    svc.get_me = AsyncMock()
    svc.change_password = AsyncMock()
    svc.get_sso_config = MagicMock()
    svc.sso_authorize = AsyncMock()
    svc.sso_callback = AsyncMock()
    # Users
    svc.create_user = AsyncMock()
    svc.query_users = AsyncMock()
    svc.get_user = AsyncMock()
    svc.update_user = AsyncMock()
    svc.delete_user = AsyncMock()
    svc.reset_password = AsyncMock()
    # Tenants
    svc.create_tenant = AsyncMock()
    svc.query_tenants = AsyncMock()
    svc.get_tenant = AsyncMock()
    svc.update_tenant = AsyncMock()
    svc.delete_tenant = AsyncMock()
    svc.switch_tenant = AsyncMock()
    # Members
    svc.add_member = AsyncMock()
    svc.query_members = AsyncMock()
    svc.update_member_role = AsyncMock()
    svc.remove_member = AsyncMock()
    # Roles
    svc.create_role = AsyncMock()
    svc.query_roles = AsyncMock()
    svc.get_role = AsyncMock()
    svc.update_role = AsyncMock()
    svc.delete_role = AsyncMock()
    # Audit
    svc.query_audit_logs = AsyncMock()
    svc.get_audit_log = AsyncMock()
    svc.cleanup_audit_logs = AsyncMock()
    # Overview
    svc.get_overview = AsyncMock()
    return svc


@pytest.fixture
def app(mock_service: MagicMock) -> FastAPI:
    _app = FastAPI()
    register_exception_handlers(_app)
    _app.include_router(router)
    set_service(mock_service)  # type: ignore[arg-type]
    return _app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# Override DB dependency
@pytest.fixture(autouse=True)
def _override_db(app: FastAPI) -> None:
    from lingshu.setting.router import get_db

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db


# ── Auth Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login(client: AsyncClient, mock_service: MagicMock) -> None:
    user = _user_resp()
    login_resp = LoginResponse(user=user)
    mock_service.login.return_value = (login_resp, "access_tok", "refresh_tok")
    mock_service._provider = MagicMock(_access_ttl=900)
    mock_service._refresh_ttl = 604800

    r = await client.post("/setting/v1/auth/login", json={"email": "user@example.com", "password": "Password1"})
    assert r.status_code == 200
    assert r.json()["data"]["user"]["email"] == "user@example.com"
    mock_service.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, mock_service: MagicMock) -> None:
    r = await client.post("/setting/v1/auth/logout")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Logged out"
    mock_service.logout.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_no_cookie(client: AsyncClient) -> None:
    r = await client.post("/setting/v1/auth/refresh")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_cookie(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.refresh.return_value = ("new_access", "new_refresh")
    mock_service._provider = MagicMock(_access_ttl=900)
    mock_service._refresh_ttl = 604800

    r = await client.post(
        "/setting/v1/auth/refresh",
        cookies={"lingshu_refresh": "old_refresh"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Token refreshed"


@pytest.mark.asyncio
async def test_me(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.get_me.return_value = _user_resp()
    r = await client.get("/setting/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["data"]["rid"] == "ri.user.u1"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, mock_service: MagicMock) -> None:
    r = await client.post("/setting/v1/auth/change-password", json={
        "current_password": "OldPass1!", "new_password": "NewPass1!",
    })
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Password changed"


@pytest.mark.asyncio
async def test_sso_config(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.get_sso_config.return_value = SsoConfigResponse(
        enabled=False, provider_name=None, authorization_url=None,
    )
    r = await client.get("/setting/v1/auth/sso/config")
    assert r.status_code == 200
    assert r.json()["data"]["enabled"] is False


@pytest.mark.asyncio
async def test_sso_authorize(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.sso_authorize.return_value = ("https://sso.example.com/authorize", "state123")
    r = await client.get("/setting/v1/auth/sso/authorize", follow_redirects=False)
    assert r.status_code == 302


@pytest.mark.asyncio
async def test_sso_callback(client: AsyncClient, mock_service: MagicMock) -> None:
    user = _user_resp()
    mock_service.sso_callback.return_value = (LoginResponse(user=user), "tok", "ref")
    mock_service._provider = MagicMock(_access_ttl=900)
    mock_service._refresh_ttl = 604800

    r = await client.post("/setting/v1/auth/sso/callback", json={"code": "abc", "state": "xyz"})
    assert r.status_code == 200


# ── User Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.create_user.return_value = _user_resp()
    r = await client.post("/setting/v1/users", json={
        "email": "new@example.com", "display_name": "New User",
        "password": "StrongPwd1", "role": "member",
    })
    assert r.status_code == 201
    assert r.json()["data"]["rid"] == "ri.user.u1"


@pytest.mark.asyncio
async def test_query_users(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.query_users.return_value = ([_user_resp()], 1)
    r = await client.post("/setting/v1/users/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    body = r.json()
    assert len(body["data"]) == 1
    assert body["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_user(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.get_user.return_value = _user_resp()
    r = await client.get("/setting/v1/users/ri.user.u1")
    assert r.status_code == 200
    assert r.json()["data"]["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.update_user.return_value = _user_resp(display_name="Updated")
    r = await client.put("/setting/v1/users/ri.user.u1", json={"display_name": "Updated"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, mock_service: MagicMock) -> None:
    r = await client.delete("/setting/v1/users/ri.user.u1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "User disabled"


@pytest.mark.asyncio
async def test_reset_password(client: AsyncClient, mock_service: MagicMock) -> None:
    r = await client.post("/setting/v1/users/ri.user.u1/reset-password", json={
        "new_password": "NewPassword1",
    })
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Password reset"


# ── Tenant Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_tenant(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.create_tenant.return_value = _tenant_resp()
    r = await client.post("/setting/v1/tenants", json={"display_name": "New Tenant"})
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_query_tenants(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.query_tenants.return_value = ([_tenant_resp()], 1)
    r = await client.post("/setting/v1/tenants/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_tenant(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.get_tenant.return_value = _tenant_resp()
    r = await client.get("/setting/v1/tenants/ri.tenant.t1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_tenant(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.update_tenant.return_value = _tenant_resp(display_name="Renamed")
    r = await client.put("/setting/v1/tenants/ri.tenant.t1", json={"display_name": "Renamed"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_tenant(client: AsyncClient, mock_service: MagicMock) -> None:
    r = await client.delete("/setting/v1/tenants/ri.tenant.t1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Tenant disabled"


@pytest.mark.asyncio
async def test_switch_tenant(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.switch_tenant.return_value = ("new_access", "new_refresh", "admin")
    mock_service._provider = MagicMock(_access_ttl=900)
    mock_service._refresh_ttl = 604800

    r = await client.post("/setting/v1/tenants/switch", json={"tenant_rid": "ri.tenant.t2"})
    assert r.status_code == 200
    assert r.json()["data"]["tenant_rid"] == "ri.tenant.t2"


# ── Member Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_member(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.add_member.return_value = _member_resp()
    r = await client.post("/setting/v1/tenants/ri.tenant.t1/members", json={
        "user_rid": "ri.user.u1", "role": "member",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_query_members(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.query_members.return_value = ([_member_resp()], 1)
    r = await client.post("/setting/v1/tenants/ri.tenant.t1/members/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


@pytest.mark.asyncio
async def test_update_member_role(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.update_member_role.return_value = _member_resp(role="viewer")
    r = await client.put(
        "/setting/v1/tenants/ri.tenant.t1/members/ri.user.u1",
        json={"role": "viewer"},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_remove_member(client: AsyncClient, mock_service: MagicMock) -> None:
    r = await client.delete("/setting/v1/tenants/ri.tenant.t1/members/ri.user.u1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Member removed"


# ── Role Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_role(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.create_role.return_value = _role_resp()
    r = await client.post("/setting/v1/roles", json={
        "name": "editor",
        "permissions": [{"resource_type": "ontology", "action": "read"}],
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_query_roles(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.query_roles.return_value = ([_role_resp()], 1)
    r = await client.post("/setting/v1/roles/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_role(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.get_role.return_value = _role_resp()
    r = await client.get("/setting/v1/roles/ri.role.r1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_role(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.update_role.return_value = _role_resp(name="editor-v2")
    r = await client.put("/setting/v1/roles/ri.role.r1", json={"name": "editor-v2"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_role(client: AsyncClient, mock_service: MagicMock) -> None:
    r = await client.delete("/setting/v1/roles/ri.role.r1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Role deleted"


# ── Audit Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_audit_logs(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.query_audit_logs.return_value = ([_audit_resp()], 1)
    r = await client.post("/setting/v1/audit-logs/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


@pytest.mark.asyncio
async def test_query_audit_logs_with_filters(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.query_audit_logs.return_value = ([_audit_resp()], 1)
    r = await client.post("/setting/v1/audit-logs/query", json={
        "filters": [{"field": "module", "operator": "eq", "value": "setting"}],
        "pagination": {"page": 1, "page_size": 10},
    })
    assert r.status_code == 200
    mock_service.query_audit_logs.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_audit_log(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.get_audit_log.return_value = _audit_resp()
    r = await client.get("/setting/v1/audit-logs/1")
    assert r.status_code == 200
    assert r.json()["data"]["log_id"] == 1


@pytest.mark.asyncio
async def test_cleanup_audit_logs(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.cleanup_audit_logs.return_value = 42
    r = await client.post("/setting/v1/audit-logs/cleanup", json={"days": 90})
    assert r.status_code == 200
    assert r.json()["data"]["deleted_count"] == 42


# ── Overview Tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_overview(client: AsyncClient, mock_service: MagicMock) -> None:
    mock_service.get_overview.return_value = OverviewResponse(
        users={"total": 5, "active": 4},
        tenants={"total": 2, "active": 2},
        recent_audit=[],
    )
    r = await client.get("/setting/v1/overview")
    assert r.status_code == 200
    assert r.json()["data"]["users"]["total"] == 5
