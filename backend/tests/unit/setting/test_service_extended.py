"""Extended tests for SettingServiceImpl — covering uncovered methods and branches."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError
from lingshu.setting.models import (
    AuditLog,
    CustomRole,
    RefreshToken,
    Tenant,
    User,
    UserTenantMembership,
)
from lingshu.setting.service import SettingServiceImpl


def _make_service(**kwargs) -> SettingServiceImpl:
    provider = MagicMock()
    provider.revoke_token = AsyncMock()
    enforcer = MagicMock()
    enforcer.check_permission = MagicMock(return_value=True)
    return SettingServiceImpl(
        provider=provider,
        enforcer=enforcer,
        refresh_ttl=kwargs.get("refresh_ttl", 604800),
    )


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_user(**overrides) -> User:
    defaults = dict(
        rid="ri.user.u1", email="user@test.com", display_name="Test User",
        password_hash="hashed", status="active",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return User(**defaults)


def _make_tenant(**overrides) -> Tenant:
    defaults = dict(
        rid="ri.tenant.t1", display_name="Test Tenant", status="active",
        config={},
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Tenant(**defaults)


def _mock_scalar(session: AsyncMock, value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute = AsyncMock(return_value=result)


# ══════════════════════════════════════════════════════════════════
# Protocol interface methods
# ══════════════════════════════════════════════════════════════════


class TestProtocolMethods:
    @patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1")
    def test_get_current_user_id(self, mock_uid):
        svc = _make_service()
        assert svc.get_current_user_id() == "ri.user.u1"

    @patch("lingshu.setting.service.get_tenant_id", return_value="ri.tenant.t1")
    def test_get_current_tenant_id(self, mock_tid):
        svc = _make_service()
        assert svc.get_current_tenant_id() == "ri.tenant.t1"

    def test_check_permission(self):
        svc = _make_service()
        assert svc.check_permission("u1", "user", "read") is True

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    @patch("lingshu.setting.service.get_request_id", return_value="req1")
    async def test_write_audit_log(self, mock_rid, mock_uid, mock_tid):
        svc = _make_service()
        session = _make_session()
        await svc.write_audit_log(
            "setting", "create", "Created user",
            resource_type="user", resource_rid="ri.user.1",
            session=session,
        )
        session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_write_audit_log_no_session(self):
        svc = _make_service()
        # Should not raise
        await svc.write_audit_log("setting", "create", "No session")


# ══════════════════════════════════════════════════════════════════
# Tenant operations
# ══════════════════════════════════════════════════════════════════


class TestTenantOperations:
    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1")
    @patch("lingshu.setting.service.get_tenant_id", return_value="ri.tenant.t1")
    async def test_create_tenant(self, mock_tid, mock_uid):
        svc = _make_service()
        session = _make_session()

        # Simulate server defaults that the DB would set
        def add_side_effect(obj):
            if hasattr(obj, "status") and obj.status is None:
                obj.status = "active"
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            if hasattr(obj, "updated_at") and obj.updated_at is None:
                obj.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            if hasattr(obj, "config") and obj.config is None:
                obj.config = {}

        session.add = MagicMock(side_effect=add_side_effect)

        from lingshu.setting.schemas.requests import CreateTenantRequest
        req = CreateTenantRequest(display_name="New Tenant")

        resp = await svc.create_tenant(req, session)
        assert resp.display_name == "New Tenant"

    @pytest.mark.asyncio
    async def test_get_tenant_not_found(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError, match="Tenant not found"):
            await svc.get_tenant("ri.tenant.missing", session)

    @pytest.mark.asyncio
    async def test_get_tenant_found(self):
        svc = _make_service()
        session = _make_session()
        tenant = _make_tenant()
        _mock_scalar(session, tenant)
        resp = await svc.get_tenant("ri.tenant.t1", session)
        assert resp.rid == "ri.tenant.t1"

    @pytest.mark.asyncio
    async def test_delete_tenant_not_found(self):
        svc = _make_service()
        session = _make_session()
        # update_fields returns None (tenant not found)
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(side_effect=[exec_result, get_result])
        with pytest.raises(AppError, match="Tenant not found"):
            await svc.delete_tenant("ri.tenant.missing", session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_role", return_value="admin")
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_query_tenants_admin(self, mock_tid, mock_uid, mock_role):
        svc = _make_service()
        session = _make_session()
        tenants = [_make_tenant()]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = tenants
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        results, total = await svc.query_tenants(session)
        assert total == 1
        assert len(results) == 1

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_role", return_value="member")
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_query_tenants_member(self, mock_tid, mock_uid, mock_role):
        svc = _make_service()
        session = _make_session()
        tenants = [_make_tenant()]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = tenants
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        results, total = await svc.query_tenants(session)
        assert total == 1


# ══════════════════════════════════════════════════════════════════
# Member operations
# ══════════════════════════════════════════════════════════════════


class TestMemberOperations:
    @pytest.mark.asyncio
    async def test_add_member_tenant_not_found(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)

        from lingshu.setting.schemas.requests import AddMemberRequest
        req = AddMemberRequest(user_rid="u1", role="member")

        with pytest.raises(AppError, match="Tenant not found"):
            await svc.add_member("ri.tenant.missing", req, session)

    @pytest.mark.asyncio
    async def test_remove_member_not_found(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)

        with pytest.raises(AppError, match="Membership not found"):
            await svc.remove_member("t1", "u1", session)

    @pytest.mark.asyncio
    async def test_remove_member_last_admin(self):
        svc = _make_service()
        session = _make_session()

        membership = MagicMock()
        membership.role = "admin"
        membership.user_rid = "u1"

        # First call: get membership
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = membership

        # Second call (list_by_tenant count): only 1 admin
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        list_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [membership]
        list_result.scalars.return_value = scalars_mock

        session.execute = AsyncMock(side_effect=[get_result, count_result, list_result])

        with pytest.raises(AppError, match="Cannot remove the last admin"):
            await svc.remove_member("t1", "u1", session)

    @pytest.mark.asyncio
    async def test_query_members_tenant_not_found(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)

        with pytest.raises(AppError, match="Tenant not found"):
            await svc.query_members("ri.tenant.missing", session)


# ══════════════════════════════════════════════════════════════════
# Role operations
# ══════════════════════════════════════════════════════════════════


class TestRoleOperations:
    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_create_role_conflict(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        existing = CustomRole(rid="r1", tenant_id="t1", name="editor", permissions=[])
        _mock_scalar(session, existing)

        from lingshu.setting.schemas.requests import CreateRoleRequest
        req = CreateRoleRequest(name="editor", permissions=[])

        with pytest.raises(AppError, match="already exists"):
            await svc.create_role(req, session)

    @pytest.mark.asyncio
    async def test_get_role_not_found(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError, match="Role not found"):
            await svc.get_role("ri.role.missing", session)

    @pytest.mark.asyncio
    async def test_delete_role_system(self):
        svc = _make_service()
        session = _make_session()
        role = CustomRole(rid="r1", tenant_id="t1", name="admin", permissions=[], is_system=True)
        _mock_scalar(session, role)
        with pytest.raises(AppError, match="System roles cannot be deleted"):
            await svc.delete_role("r1", session)

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError, match="Role not found"):
            await svc.delete_role("ri.role.missing", session)

    @pytest.mark.asyncio
    async def test_update_role_system(self):
        svc = _make_service()
        session = _make_session()
        role = CustomRole(rid="r1", tenant_id="t1", name="admin", permissions=[], is_system=True)
        _mock_scalar(session, role)

        from lingshu.setting.schemas.requests import UpdateRoleRequest
        req = UpdateRoleRequest(name="new_name")
        with pytest.raises(AppError, match="System roles cannot be modified"):
            await svc.update_role("r1", req, session)


# ══════════════════════════════════════════════════════════════════
# Audit log operations
# ══════════════════════════════════════════════════════════════════


class TestAuditLogOperations:
    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_cleanup_audit_logs(self, mock_tid):
        svc = _make_service()
        session = _make_session()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 10
        session.execute = AsyncMock(side_effect=[count_result, AsyncMock(), None])

        count = await svc.cleanup_audit_logs(session, days=30)
        assert count == 10

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_get_audit_log_not_found(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError, match="Audit log not found"):
            await svc.get_audit_log(999, session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_get_audit_log_found(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        log = AuditLog(
            log_id=1, tenant_id="t1", module="setting", event_type="create",
            user_id="u1", action="test",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        _mock_scalar(session, log)
        resp = await svc.get_audit_log(1, session)
        assert resp.log_id == 1


# ══════════════════════════════════════════════════════════════════
# Overview
# ══════════════════════════════════════════════════════════════════


class TestOverview:
    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_get_overview(self, mock_tid):
        svc = _make_service()
        session = _make_session()

        # count_by_status
        status_result = MagicMock()
        status_result.all.return_value = [("active", 5), ("disabled", 1)]

        # tenant count
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        # recent audit logs
        recent_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        recent_result.scalars.return_value = scalars_mock

        session.execute = AsyncMock(side_effect=[status_result, count_result, recent_result])

        overview = await svc.get_overview(session)
        assert overview.users["total"] == 6
        assert overview.tenants["total"] == 2


# ══════════════════════════════════════════════════════════════════
# SSO operations
# ══════════════════════════════════════════════════════════════════


class TestSsoOperations:
    @pytest.mark.asyncio
    async def test_sso_authorize_not_configured(self):
        svc = _make_service()
        with pytest.raises(AppError, match="SSO is not configured"):
            await svc.sso_authorize()

    @pytest.mark.asyncio
    async def test_sso_callback_not_configured(self):
        svc = _make_service()
        session = _make_session()
        with pytest.raises(AppError, match="SSO is not configured"):
            await svc.sso_callback("code", "state", session)

    def test_get_sso_config_disabled(self):
        svc = _make_service()
        resp = svc.get_sso_config()
        assert resp.enabled is False

    def test_get_sso_config_enabled(self):
        svc = _make_service()
        settings = MagicMock()
        settings.sso_enabled = True
        settings.oidc_provider_name = "Okta"
        svc._settings = settings
        resp = svc.get_sso_config()
        assert resp.enabled is True
        assert resp.provider_name == "Okta"


# ══════════════════════════════════════════════════════════════════
# User operations
# ══════════════════════════════════════════════════════════════════


class TestUserOperations:
    @pytest.mark.asyncio
    async def test_delete_user_not_found(self):
        svc = _make_service()
        session = _make_session()
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(side_effect=[exec_result, get_result])
        with pytest.raises(AppError, match="User not found"):
            await svc.delete_user("ri.user.missing", session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    async def test_change_password_wrong_current(self, mock_uid):
        svc = _make_service()
        session = _make_session()
        # Use a real bcrypt hash for "correct_password"
        from lingshu.setting.auth.password import hash_password
        real_hash = hash_password("correct_password")
        user = _make_user(password_hash=real_hash)
        _mock_scalar(session, user)

        from lingshu.setting.schemas.requests import ChangePasswordRequest
        req = ChangePasswordRequest(current_password="wrong", new_password="NewPass123!")
        with pytest.raises(AppError, match="Current password is incorrect"):
            await svc.change_password(req, session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_update_user_no_fields(self, mock_tid):
        svc = _make_service()
        session = _make_session()

        from lingshu.setting.schemas.requests import UpdateUserRequest
        req = UpdateUserRequest()
        with pytest.raises(AppError, match="No fields to update"):
            await svc.update_user("ri.user.u1", req, session)

    @pytest.mark.asyncio
    async def test_reset_password_weak(self):
        svc = _make_service()
        session = _make_session()

        from lingshu.setting.schemas.requests import ResetPasswordRequest
        # Password passes Pydantic min_length but fails validate_password_strength
        # (needs at least one letter AND one digit)
        req = ResetPasswordRequest(new_password="noodigits")
        with pytest.raises(AppError):
            await svc.reset_password("ri.user.u1", req, session)

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(self):
        svc = _make_service()
        session = _make_session()
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(side_effect=[exec_result, get_result])

        from lingshu.setting.schemas.requests import ResetPasswordRequest
        req = ResetPasswordRequest(new_password="ValidPass123!")
        with pytest.raises(AppError, match="User not found"):
            await svc.reset_password("ri.user.missing", req, session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_get_user_found(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        user = _make_user()
        membership = MagicMock()
        membership.role = "admin"

        get_user_result = MagicMock()
        get_user_result.scalar_one_or_none.return_value = user
        get_membership_result = MagicMock()
        get_membership_result.scalar_one_or_none.return_value = membership
        session.execute = AsyncMock(side_effect=[get_user_result, get_membership_result])

        resp = await svc.get_user("ri.user.u1", session)
        assert resp.rid == "ri.user.u1"
        assert resp.role == "admin"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError, match="User not found"):
            await svc.get_user("ri.user.missing", session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_update_user_success(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        updated = _make_user(display_name="Updated Name")
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[exec_result, get_result])

        from lingshu.setting.schemas.requests import UpdateUserRequest
        req = UpdateUserRequest(display_name="Updated Name")
        resp = await svc.update_user("ri.user.u1", req, session)
        assert resp.display_name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_user_not_found(self):
        svc = _make_service()
        session = _make_session()
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(side_effect=[exec_result, get_result])

        from lingshu.setting.schemas.requests import UpdateUserRequest
        req = UpdateUserRequest(display_name="X")
        with pytest.raises(AppError, match="User not found"):
            await svc.update_user("ri.user.missing", req, session)


# ══════════════════════════════════════════════════════════════════
# Login / Logout / Refresh / Switch Tenant
# ══════════════════════════════════════════════════════════════════


class TestAuthOperations:
    @pytest.mark.asyncio
    async def test_login_success(self):
        svc = _make_service()
        session = _make_session()

        from lingshu.setting.auth.password import hash_password
        pw_hash = hash_password("Password123!")
        user = _make_user(password_hash=pw_hash)
        membership = MagicMock()
        membership.user_rid = user.rid
        membership.tenant_rid = "ri.tenant.t1"
        membership.role = "admin"
        membership.is_default = True
        tenant = _make_tenant()

        # get_by_email, get_default_tenant, get_by_rid (tenant)
        email_result = MagicMock()
        email_result.scalar_one_or_none.return_value = user
        default_result = MagicMock()
        default_result.scalar_one_or_none.return_value = membership
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        session.execute = AsyncMock(side_effect=[email_result, default_result, tenant_result])

        svc._provider.issue_access_token.return_value = "access_token"
        svc._provider.issue_refresh_token.return_value = ("refresh_raw", "refresh_hash")

        resp, access, refresh = await svc.login("user@test.com", "Password123!", session)
        assert access == "access_token"
        assert refresh == "refresh_raw"
        assert resp.user.rid == user.rid

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)  # user not found

        with pytest.raises(AppError, match="Invalid email or password"):
            await svc.login("no@user.com", "wrong", session)

    @pytest.mark.asyncio
    async def test_login_disabled_user(self):
        svc = _make_service()
        session = _make_session()

        from lingshu.setting.auth.password import hash_password
        user = _make_user(password_hash=hash_password("Pass123!"), status="disabled")
        _mock_scalar(session, user)

        with pytest.raises(AppError, match="User account is disabled"):
            await svc.login("user@test.com", "Pass123!", session)

    @pytest.mark.asyncio
    async def test_login_no_default_tenant_uses_first(self):
        svc = _make_service()
        session = _make_session()

        from lingshu.setting.auth.password import hash_password
        user = _make_user(password_hash=hash_password("Pass123!"))
        membership = MagicMock()
        membership.user_rid = user.rid
        membership.tenant_rid = "ri.tenant.t1"
        membership.role = "member"
        membership.is_default = False
        tenant = _make_tenant()

        # get_by_email, get_default_tenant (None), list_by_user, get_by_rid (tenant)
        email_result = MagicMock()
        email_result.scalar_one_or_none.return_value = user
        default_result = MagicMock()
        default_result.scalar_one_or_none.return_value = None  # no default
        list_scalars = MagicMock()
        list_scalars.all.return_value = [membership]
        list_result = MagicMock()
        list_result.scalars.return_value = list_scalars
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        session.execute = AsyncMock(side_effect=[
            email_result, default_result, list_result, tenant_result,
        ])

        svc._provider.issue_access_token.return_value = "at"
        svc._provider.issue_refresh_token.return_value = ("rt", "rh")

        resp, _, _ = await svc.login("user@test.com", "Pass123!", session)
        assert resp.user.role == "member"

    @pytest.mark.asyncio
    async def test_logout(self):
        svc = _make_service()
        session = _make_session()

        payload = MagicMock()
        payload.jti = "jwt-id"
        payload.exp = 1234567890
        svc._provider.validate_token.return_value = payload

        await svc.logout("access_token", "refresh_raw", session)
        svc._provider.revoke_token.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logout_expired_token(self):
        svc = _make_service()
        session = _make_session()

        svc._provider.validate_token.side_effect = ValueError("expired")

        # Should not raise even with expired token
        await svc.logout("expired_token", None, session)

    @pytest.mark.asyncio
    async def test_refresh_success(self):
        svc = _make_service()
        session = _make_session()

        token = MagicMock()
        token.user_rid = "u1"
        token.tenant_rid = "t1"
        token.revoked_at = None
        token.expires_at = datetime(2030, 1, 1)

        # get_by_hash, revoke, get membership
        hash_result = MagicMock()
        hash_result.scalar_one_or_none.return_value = token
        membership = MagicMock()
        membership.role = "admin"
        membership_result = MagicMock()
        membership_result.scalar_one_or_none.return_value = membership
        session.execute = AsyncMock(side_effect=[
            hash_result, AsyncMock(), membership_result,  # get, revoke, get membership
        ])

        svc._provider.issue_access_token.return_value = "new_at"
        svc._provider.issue_refresh_token.return_value = ("new_rt", "new_rh")

        at, rt = await svc.refresh("old_refresh_token", session)
        assert at == "new_at"
        assert rt == "new_rt"

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)

        with pytest.raises(AppError, match="invalid or expired"):
            await svc.refresh("bad_token", session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    async def test_switch_tenant_success(self, mock_uid):
        svc = _make_service()
        session = _make_session()

        membership = MagicMock()
        membership.role = "member"
        tenant = _make_tenant()

        get_membership_result = MagicMock()
        get_membership_result.scalar_one_or_none.return_value = membership
        get_tenant_result = MagicMock()
        get_tenant_result.scalar_one_or_none.return_value = tenant
        session.execute = AsyncMock(side_effect=[get_membership_result, get_tenant_result])

        svc._provider.issue_access_token.return_value = "at"
        svc._provider.issue_refresh_token.return_value = ("rt", "rh")

        from lingshu.setting.schemas.requests import SwitchTenantRequest
        req = SwitchTenantRequest(tenant_rid="ri.tenant.t1")
        at, rt, role = await svc.switch_tenant(req, session)
        assert at == "at"
        assert role == "member"

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    async def test_switch_tenant_not_member(self, mock_uid):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)

        from lingshu.setting.schemas.requests import SwitchTenantRequest
        req = SwitchTenantRequest(tenant_rid="ri.tenant.t99")
        with pytest.raises(AppError, match="not a member"):
            await svc.switch_tenant(req, session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_get_me(self, mock_tid, mock_uid):
        svc = _make_service()
        session = _make_session()

        user = _make_user()
        membership = MagicMock()
        membership.role = "admin"
        tenant = _make_tenant()

        get_user_result = MagicMock()
        get_user_result.scalar_one_or_none.return_value = user
        get_membership_result = MagicMock()
        get_membership_result.scalar_one_or_none.return_value = membership
        get_tenant_result = MagicMock()
        get_tenant_result.scalar_one_or_none.return_value = tenant
        session.execute = AsyncMock(side_effect=[
            get_user_result, get_membership_result, get_tenant_result,
        ])

        resp = await svc.get_me(session)
        assert resp.rid == "ri.user.u1"
        assert resp.role == "admin"

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_get_me_not_found(self, mock_tid, mock_uid):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError, match="User not found"):
            await svc.get_me(session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_user_id", return_value="u1")
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_query_users(self, mock_tid, mock_uid):
        svc = _make_service()
        session = _make_session()

        users = [_make_user()]
        membership = MagicMock()
        membership.role = "admin"

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        list_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = users
        list_result.scalars.return_value = scalars_mock
        membership_result = MagicMock()
        membership_result.scalar_one_or_none.return_value = membership
        session.execute = AsyncMock(side_effect=[count_result, list_result, membership_result])

        results, total = await svc.query_users(session)
        assert total == 1
        assert len(results) == 1
        assert results[0].role == "admin"

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_create_user_email_exists(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        existing = _make_user()
        _mock_scalar(session, existing)

        from lingshu.setting.schemas.requests import CreateUserRequest
        req = CreateUserRequest(
            email="user@test.com", display_name="User",
            password="ValidPass1!", role="member",
        )
        with pytest.raises(AppError, match="already registered"):
            await svc.create_user(req, session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_create_user_weak_password(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)  # email not taken

        from lingshu.setting.schemas.requests import CreateUserRequest
        req = CreateUserRequest(
            email="new@test.com", display_name="User",
            password="nodigits!", role="member",
        )
        with pytest.raises(AppError):
            await svc.create_user(req, session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_create_user_success(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)  # email not taken

        def add_side_effect(obj):
            if hasattr(obj, "status") and obj.status is None:
                obj.status = "active"
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            if hasattr(obj, "updated_at") and obj.updated_at is None:
                obj.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        session.add = MagicMock(side_effect=add_side_effect)

        from lingshu.setting.schemas.requests import CreateUserRequest
        req = CreateUserRequest(
            email="new@test.com", display_name="New User",
            password="ValidPass1!", role="member",
        )
        resp = await svc.create_user(req, session)
        assert resp.email == "new@test.com"
        svc._enforcer.sync_user_role.assert_called()


class TestMemberOperationsExtended:
    @pytest.mark.asyncio
    async def test_add_member_success(self):
        svc = _make_service()
        session = _make_session()

        tenant = _make_tenant()
        user = _make_user()
        # get_by_rid (tenant), get_by_rid (user), get membership (none), create
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        membership_result = MagicMock()
        membership_result.scalar_one_or_none.return_value = None  # not already member

        session.execute = AsyncMock(side_effect=[tenant_result, user_result, membership_result])

        def add_side_effect(obj):
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        session.add = MagicMock(side_effect=add_side_effect)

        from lingshu.setting.schemas.requests import AddMemberRequest
        req = AddMemberRequest(user_rid="ri.user.u1", role="member")
        resp = await svc.add_member("ri.tenant.t1", req, session)
        assert resp.role == "member"

    @pytest.mark.asyncio
    async def test_add_member_already_member(self):
        svc = _make_service()
        session = _make_session()

        tenant = _make_tenant()
        user = _make_user()
        existing_membership = MagicMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        membership_result = MagicMock()
        membership_result.scalar_one_or_none.return_value = existing_membership

        session.execute = AsyncMock(side_effect=[tenant_result, user_result, membership_result])

        from lingshu.setting.schemas.requests import AddMemberRequest
        req = AddMemberRequest(user_rid="ri.user.u1", role="member")
        with pytest.raises(AppError, match="already a member"):
            await svc.add_member("ri.tenant.t1", req, session)

    @pytest.mark.asyncio
    async def test_update_member_role_success(self):
        svc = _make_service()
        session = _make_session()

        membership = MagicMock()
        membership.role = "member"
        updated_membership = MagicMock()
        updated_membership.role = "admin"
        updated_membership.is_default = True
        updated_membership.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        user = _make_user()

        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = membership
        update_exec = AsyncMock()
        updated_result = MagicMock()
        updated_result.scalar_one_or_none.return_value = updated_membership
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user

        session.execute = AsyncMock(side_effect=[
            get_result, update_exec, updated_result, user_result,
        ])

        from lingshu.setting.schemas.requests import UpdateMemberRoleRequest
        req = UpdateMemberRoleRequest(role="admin")
        resp = await svc.update_member_role("t1", "u1", req, session)
        assert resp.role == "admin"

    @pytest.mark.asyncio
    async def test_query_members_success(self):
        svc = _make_service()
        session = _make_session()

        tenant = _make_tenant()
        membership = MagicMock()
        membership.user_rid = "ri.user.u1"
        membership.role = "admin"
        membership.is_default = True
        membership.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        user = _make_user()

        # get_by_rid (tenant), list_by_tenant (count + data), get_by_rid (user)
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        list_scalars = MagicMock()
        list_scalars.all.return_value = [membership]
        list_result = MagicMock()
        list_result.scalars.return_value = list_scalars
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user

        session.execute = AsyncMock(side_effect=[
            tenant_result, count_result, list_result, user_result,
        ])

        results, total = await svc.query_members("ri.tenant.t1", session)
        assert total == 1
        assert len(results) == 1


class TestRoleOperationsExtended:
    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_create_role_success(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)  # no existing role with same name

        def add_side_effect(obj):
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            if hasattr(obj, "updated_at") and obj.updated_at is None:
                obj.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        session.add = MagicMock(side_effect=add_side_effect)

        from lingshu.setting.schemas.requests import CreateRoleRequest
        req = CreateRoleRequest(name="custom_role", permissions=[], description="A custom role")
        resp = await svc.create_role(req, session)
        assert resp.name == "custom_role"

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_query_roles(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        role = CustomRole(
            rid="r1", tenant_id="t1", name="admin",
            permissions=[{"resource_type": "*", "action": "*"}],
            is_system=True,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        list_scalars = MagicMock()
        list_scalars.all.return_value = [role]
        list_result = MagicMock()
        list_result.scalars.return_value = list_scalars
        session.execute = AsyncMock(side_effect=[count_result, list_result])

        results, total = await svc.query_roles(session)
        assert total == 1
        assert results[0].name == "admin"

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_assign_role_to_user(self, mock_tid):
        svc = _make_service()
        session = _make_session()

        membership = MagicMock()
        membership.role = "member"
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = membership

        session.execute = AsyncMock(side_effect=[get_result, AsyncMock(), MagicMock()])

        await svc.assign_role_to_user("u1", "admin", session)
        svc._enforcer.remove_user_role.assert_called_with("u1", "member")
        svc._enforcer.sync_user_role.assert_called_with("u1", "admin")

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_assign_role_membership_not_found(self, mock_tid):
        svc = _make_service()
        session = _make_session()
        _mock_scalar(session, None)

        with pytest.raises(AppError, match="Membership not found"):
            await svc.assign_role_to_user("u1", "admin", session)

    @pytest.mark.asyncio
    @patch("lingshu.setting.service.get_tenant_id", return_value="t1")
    async def test_query_audit_logs(self, mock_tid):
        svc = _make_service()
        session = _make_session()

        log = AuditLog(
            log_id=1, tenant_id="t1", module="setting", event_type="create",
            user_id="u1", action="test",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        list_scalars = MagicMock()
        list_scalars.all.return_value = [log]
        list_result = MagicMock()
        list_result.scalars.return_value = list_scalars
        session.execute = AsyncMock(side_effect=[count_result, list_result])

        results, total = await svc.query_audit_logs(session, module="setting")
        assert total == 1
        assert results[0].module == "setting"
