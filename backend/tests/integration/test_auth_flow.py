"""Integration tests for complete auth flows across multiple service layers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.setting.auth.password import hash_password
from lingshu.setting.auth.provider import BuiltinProvider
from lingshu.setting.authz.enforcer import PermissionEnforcer
from lingshu.setting.models import (
    RefreshToken,
    Tenant,
    User,
    UserTenantMembership,
)
from lingshu.setting.schemas.requests import (
    ChangePasswordRequest,
    CreateTenantRequest,
    SwitchTenantRequest,
)
from lingshu.setting.service import SettingServiceImpl


# ── Helpers ───────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _make_user(
    rid: str = "ri.user.u1",
    email: str = "user@example.com",
    password: str = "Password1",
    status: str = "active",
) -> User:
    u = User(
        rid=rid,
        email=email,
        display_name="Test User",
        password_hash=hash_password(password),
        status=status,
    )
    u.created_at = _now()
    u.updated_at = _now()
    return u


def _make_tenant(rid: str = "ri.tenant.t1", status: str = "active") -> Tenant:
    t = Tenant(rid=rid, display_name="Default Tenant", status=status, config={})
    t.created_at = _now()
    t.updated_at = _now()
    return t


def _make_membership(
    user_rid: str = "ri.user.u1",
    tenant_rid: str = "ri.tenant.t1",
    role: str = "admin",
    is_default: bool = True,
) -> UserTenantMembership:
    m = UserTenantMembership(
        user_rid=user_rid, tenant_rid=tenant_rid, role=role, is_default=is_default,
    )
    m.created_at = _now()
    return m


def _make_refresh_token(
    user_rid: str = "ri.user.u1",
    tenant_rid: str = "ri.tenant.t1",
    token_hash: str = "hash123",
    expired: bool = False,
) -> RefreshToken:
    exp = _now() + (timedelta(days=-1) if expired else timedelta(days=7))
    rt = RefreshToken(
        token_hash=token_hash,
        user_rid=user_rid,
        tenant_rid=tenant_rid,
        expires_at=exp,
        revoked_at=None,
    )
    rt.created_at = _now()
    return rt


def _build_service() -> SettingServiceImpl:
    provider = MagicMock(spec=BuiltinProvider)
    provider.issue_access_token.return_value = "access_tok"
    provider.issue_refresh_token.return_value = ("refresh_raw", "refresh_hash")
    provider._access_ttl = 900
    provider.validate_token.return_value = MagicMock(jti="jti1", exp=9999999999)
    provider.revoke_token = AsyncMock()

    enforcer = PermissionEnforcer()
    enforcer.seed_policies()
    return SettingServiceImpl(provider=provider, enforcer=enforcer)


def _mock_session() -> AsyncMock:
    s = AsyncMock()
    s.commit = AsyncMock()
    s.flush = AsyncMock()
    return s


# ── Test classes ──────────────────────────────────────────────────


class TestLoginGetUserChangePasswordRelogin:
    """Login -> get_me -> change_password -> login with new password."""

    async def test_full_flow(self) -> None:
        service = _build_service()
        session = _mock_session()
        user = _make_user(password="Password1")
        tenant = _make_tenant()
        membership = _make_membership()

        with (
            patch("lingshu.setting.service.UserRepository") as MockUserRepo,
            patch("lingshu.setting.service.MembershipRepository") as MockMemberRepo,
            patch("lingshu.setting.service.TenantRepository") as MockTenantRepo,
            patch("lingshu.setting.service.RefreshTokenRepository") as MockRefreshRepo,
        ):
            MockUserRepo.return_value.get_by_email = AsyncMock(return_value=user)
            MockUserRepo.return_value.get_by_rid = AsyncMock(return_value=user)
            MockUserRepo.return_value.update_fields = AsyncMock(return_value=user)
            MockMemberRepo.return_value.get_default_tenant = AsyncMock(return_value=membership)
            MockMemberRepo.return_value.get = AsyncMock(return_value=membership)
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=tenant)
            MockRefreshRepo.return_value.create = AsyncMock()

            # Step 1: Login
            resp, access, refresh = await service.login("user@example.com", "Password1", session)
            assert resp.user.rid == "ri.user.u1"
            assert access == "access_tok"

            # Step 2: Get current user
            with (
                patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
                patch("lingshu.setting.service.get_tenant_id", return_value="ri.tenant.t1"),
            ):
                me = await service.get_me(session)
                assert me.email == "user@example.com"

            # Step 3: Change password
            with patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"):
                req = ChangePasswordRequest(current_password="Password1", new_password="NewPass99")
                await service.change_password(req, session)
                MockUserRepo.return_value.update_fields.assert_awaited()

            # Step 4: Login again (simulated with new user hash)
            new_user = _make_user(password="NewPass99")
            MockUserRepo.return_value.get_by_email = AsyncMock(return_value=new_user)
            resp2, _, _ = await service.login("user@example.com", "NewPass99", session)
            assert resp2.user.rid == "ri.user.u1"


class TestLoginCreateTenantSwitchTenant:
    """Login -> create tenant -> switch tenant -> verify new token."""

    async def test_full_flow(self) -> None:
        service = _build_service()
        session = _mock_session()
        user = _make_user()
        tenant1 = _make_tenant()
        tenant2 = _make_tenant(rid="ri.tenant.t2")
        membership1 = _make_membership()

        with (
            patch("lingshu.setting.service.UserRepository") as MockUserRepo,
            patch("lingshu.setting.service.MembershipRepository") as MockMemberRepo,
            patch("lingshu.setting.service.TenantRepository") as MockTenantRepo,
            patch("lingshu.setting.service.RefreshTokenRepository") as MockRefreshRepo,
            patch("lingshu.setting.service.generate_rid", return_value="ri.tenant.t2"),
            patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
            patch("lingshu.setting.service.get_tenant_id", return_value="ri.tenant.t1"),
        ):
            MockUserRepo.return_value.get_by_email = AsyncMock(return_value=user)
            MockMemberRepo.return_value.get_default_tenant = AsyncMock(return_value=membership1)
            MockMemberRepo.return_value.get = AsyncMock(
                return_value=_make_membership(tenant_rid="ri.tenant.t2", role="admin"),
            )
            MockMemberRepo.return_value.create = AsyncMock(
                return_value=_make_membership(tenant_rid="ri.tenant.t2"),
            )
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=tenant2)
            MockTenantRepo.return_value.create = AsyncMock(return_value=tenant2)
            MockRefreshRepo.return_value.create = AsyncMock()

            # Step 1: Login to first tenant
            resp, _, _ = await service.login("user@example.com", "Password1", session)
            assert resp.user.rid == "ri.user.u1"

            # Step 2: Create second tenant
            req = CreateTenantRequest(display_name="Second Tenant")
            created = await service.create_tenant(req, session)
            assert created.rid == "ri.tenant.t2"

            # Step 3: Switch to second tenant
            switch_req = SwitchTenantRequest(tenant_rid="ri.tenant.t2")
            access, refresh, role = await service.switch_tenant(switch_req, session)
            assert access == "access_tok"
            assert role == "admin"


class TestLoginLogoutReject:
    """Login -> logout -> verify token rejected."""

    async def test_full_flow(self) -> None:
        service = _build_service()
        session = _mock_session()

        # Logout should revoke the token
        with patch("lingshu.setting.service.RefreshTokenRepository") as MockRefreshRepo:
            MockRefreshRepo.return_value.revoke = AsyncMock()
            await service.logout("access_tok", "refresh_raw", session)
            service._provider.validate_token.assert_called_once_with("access_tok")
            service._provider.revoke_token.assert_awaited_once()
            MockRefreshRepo.return_value.revoke.assert_awaited_once()


class TestRefreshTokenFlow:
    """Test refresh token round-trip."""

    async def test_refresh_success(self) -> None:
        service = _build_service()
        session = _mock_session()
        rt = _make_refresh_token()
        membership = _make_membership()

        with (
            patch("lingshu.setting.service.RefreshTokenRepository") as MockRefreshRepo,
            patch("lingshu.setting.service.MembershipRepository") as MockMemberRepo,
        ):
            repo = MockRefreshRepo.return_value
            repo.get_by_hash = AsyncMock(return_value=rt)
            repo.is_valid = MagicMock(return_value=True)
            repo.revoke = AsyncMock()
            repo.create = AsyncMock()
            MockMemberRepo.return_value.get = AsyncMock(return_value=membership)

            access, new_refresh = await service.refresh("refresh_raw", session)
            assert access == "access_tok"
            assert new_refresh == "refresh_raw"
            repo.revoke.assert_awaited_once()
            repo.create.assert_awaited_once()

    async def test_refresh_expired_token(self) -> None:
        service = _build_service()
        session = _mock_session()
        rt = _make_refresh_token(expired=True)

        with patch("lingshu.setting.service.RefreshTokenRepository") as MockRefreshRepo:
            repo = MockRefreshRepo.return_value
            repo.get_by_hash = AsyncMock(return_value=rt)
            repo.is_valid = MagicMock(return_value=False)

            with pytest.raises(AppError) as exc_info:
                await service.refresh("refresh_raw", session)
            assert exc_info.value.code == ErrorCode.SETTING_AUTH_TOKEN_EXPIRED

    async def test_refresh_revoked_token(self) -> None:
        service = _build_service()
        session = _mock_session()

        with patch("lingshu.setting.service.RefreshTokenRepository") as MockRefreshRepo:
            MockRefreshRepo.return_value.get_by_hash = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.refresh("bad_token", session)
            assert exc_info.value.code == ErrorCode.SETTING_AUTH_TOKEN_EXPIRED


class TestLoginDisabledUser:
    """Login with disabled user should be rejected."""

    async def test_disabled_user_login(self) -> None:
        service = _build_service()
        session = _mock_session()
        user = _make_user(status="disabled")

        with patch("lingshu.setting.service.UserRepository") as MockUserRepo:
            MockUserRepo.return_value.get_by_email = AsyncMock(return_value=user)

            with pytest.raises(AppError) as exc_info:
                await service.login("user@example.com", "Password1", session)
            assert exc_info.value.code == ErrorCode.SETTING_PERMISSION_DENIED


class TestLoginInvalidCredentials:
    """Login with wrong password should fail."""

    async def test_wrong_password(self) -> None:
        service = _build_service()
        session = _mock_session()
        user = _make_user(password="Password1")

        with patch("lingshu.setting.service.UserRepository") as MockUserRepo:
            MockUserRepo.return_value.get_by_email = AsyncMock(return_value=user)

            with pytest.raises(AppError) as exc_info:
                await service.login("user@example.com", "WrongPass1", session)
            assert exc_info.value.code == ErrorCode.SETTING_AUTH_INVALID_CREDENTIALS

    async def test_nonexistent_user(self) -> None:
        service = _build_service()
        session = _mock_session()

        with patch("lingshu.setting.service.UserRepository") as MockUserRepo:
            MockUserRepo.return_value.get_by_email = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.login("nobody@example.com", "Password1", session)
            assert exc_info.value.code == ErrorCode.SETTING_AUTH_INVALID_CREDENTIALS


class TestSwitchTenantNotMember:
    """Switch to tenant where user is not a member should fail."""

    async def test_not_a_member(self) -> None:
        service = _build_service()
        session = _mock_session()

        with (
            patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
            patch("lingshu.setting.service.MembershipRepository") as MockMemberRepo,
            patch("lingshu.setting.service.TenantRepository") as MockTenantRepo,
            patch("lingshu.setting.service.RefreshTokenRepository"),
        ):
            MockMemberRepo.return_value.get = AsyncMock(return_value=None)
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.switch_tenant(
                    SwitchTenantRequest(tenant_rid="ri.tenant.t99"), session,
                )
            assert exc_info.value.code == ErrorCode.SETTING_PERMISSION_DENIED
