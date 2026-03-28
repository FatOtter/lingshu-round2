"""BS-12: Complete SSO Login Flow.

Scenario: An enterprise user logs in through SSO (OIDC) for the first time,
triggering JIT provisioning.

Steps:
1. OIDC config loaded
2. Authorization code exchange
3. Token validation
4. JIT user provisioning
5. User can access system
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.setting.auth.jit_provisioning import JitProvisioner
from lingshu.setting.auth.oidc_provider import OidcConfig, OidcProvider, OidcUserInfo
from lingshu.setting.auth.password import hash_password
from lingshu.setting.auth.provider import BuiltinProvider
from lingshu.setting.authz.enforcer import PermissionEnforcer
from lingshu.setting.models import (
    RefreshToken,
    Tenant,
    User,
    UserTenantMembership,
)
from lingshu.setting.schemas.responses import SsoConfigResponse
from lingshu.setting.service import SettingServiceImpl

from .conftest import mock_session


def _now() -> datetime:
    return datetime.now(UTC)


def _make_user(
    rid: str = "ri.user.sso1",
    email: str = "john@company.com",
    display_name: str = "John Doe",
    status: str = "active",
) -> User:
    u = User(
        rid=rid,
        email=email,
        display_name=display_name,
        password_hash="SSO_MANAGED",
        status=status,
    )
    u.created_at = _now()
    u.updated_at = _now()
    return u


def _make_tenant(
    rid: str = "ri.tenant.default",
    display_name: str = "Default",
) -> Tenant:
    t = Tenant(rid=rid, display_name=display_name, status="active", config={})
    t.created_at = _now()
    t.updated_at = _now()
    return t


def _make_membership(
    user_rid: str = "ri.user.sso1",
    tenant_rid: str = "ri.tenant.default",
    role: str = "member",
) -> UserTenantMembership:
    m = UserTenantMembership(
        user_rid=user_rid, tenant_rid=tenant_rid, role=role, is_default=True,
    )
    m.created_at = _now()
    return m


def _build_service_with_sso() -> SettingServiceImpl:
    """Build SettingServiceImpl with SSO configured."""
    provider = MagicMock(spec=BuiltinProvider)
    provider.issue_access_token.return_value = "access_tok_sso"
    provider.issue_refresh_token.return_value = ("refresh_raw_sso", "refresh_hash_sso")
    provider._access_ttl = 900

    enforcer = PermissionEnforcer()
    enforcer.seed_policies()

    settings = MagicMock()
    settings.sso_enabled = True
    settings.oidc_issuer_url = "https://idp.example.com"
    settings.oidc_client_id = "client_id"
    settings.oidc_client_secret = "client_secret"
    settings.oidc_redirect_uri = "http://localhost:3100/callback"
    settings.oidc_provider_name = "Company IdP"

    service = SettingServiceImpl(
        provider=provider,
        enforcer=enforcer,
        settings=settings,
    )
    return service


def _build_service_without_sso() -> SettingServiceImpl:
    """Build SettingServiceImpl without SSO."""
    provider = MagicMock(spec=BuiltinProvider)
    enforcer = PermissionEnforcer()
    return SettingServiceImpl(provider=provider, enforcer=enforcer)


class TestSSOLogin:
    """Complete SSO login flow scenario."""

    def test_step1_sso_config_loaded(self) -> None:
        """Step 1: SSO configuration is correctly loaded."""
        service = _build_service_with_sso()

        config = service.get_sso_config()
        assert config.enabled is True
        assert config.provider_name == "Company IdP"

    def test_step1_sso_not_configured(self) -> None:
        """Step 1 error: SSO not configured returns disabled."""
        service = _build_service_without_sso()

        config = service.get_sso_config()
        assert config.enabled is False

    async def test_step2_sso_authorize_generates_url(self) -> None:
        """Step 2: SSO authorize generates redirect URL."""
        service = _build_service_with_sso()

        # Mock the OIDC provider's discovery and URL generation
        service._oidc_provider = AsyncMock()
        service._oidc_provider.get_authorization_url = AsyncMock(
            return_value="https://idp.example.com/auth?client_id=xyz&state=abc",
        )

        url, state = await service.sso_authorize()
        assert "idp.example.com" in url
        assert len(state) > 0

    async def test_step2_sso_authorize_not_configured(self) -> None:
        """Step 2 error: SSO authorize fails when not configured."""
        service = _build_service_without_sso()

        with pytest.raises(AppError) as exc_info:
            await service.sso_authorize()
        assert exc_info.value.code == ErrorCode.COMMON_INVALID_INPUT

    async def test_step3_sso_callback_new_user_jit(self) -> None:
        """Step 3-4: SSO callback with JIT provisioning for new user."""
        service = _build_service_with_sso()
        session = mock_session()

        user = _make_user()
        tenant = _make_tenant()
        membership = _make_membership()

        # Mock OIDC provider
        service._oidc_provider = AsyncMock()
        service._oidc_provider.exchange_code = AsyncMock(
            return_value={"access_token": "idp_token_123"},
        )
        service._oidc_provider.get_userinfo = AsyncMock(
            return_value=OidcUserInfo(
                sub="user123",
                email="john@company.com",
                name="John Doe",
                raw_claims={"sub": "user123"},
            ),
        )

        # Mock JIT provisioner
        service._jit_provisioner = AsyncMock()
        service._jit_provisioner.provision_user = AsyncMock(return_value=user)

        with (
            patch("lingshu.setting.service.TenantRepository") as MockTenantRepo,
            patch("lingshu.setting.service.MembershipRepository") as MockMemberRepo,
            patch("lingshu.setting.service.RefreshTokenRepository") as MockRefreshRepo,
        ):
            MockTenantRepo.return_value.list_all = AsyncMock(
                return_value=([tenant], 1),
            )
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=tenant)
            MockMemberRepo.return_value.get_default_tenant = AsyncMock(
                return_value=membership,
            )
            MockRefreshRepo.return_value.create = AsyncMock()

            response, access_token, refresh = await service.sso_callback(
                "auth_code_123", "state_abc", session,
            )

            assert response.user.email == "john@company.com"
            assert response.user.display_name == "John Doe"
            assert access_token == "access_tok_sso"
            assert response.user.role == "member"

    async def test_step4_jit_provisions_new_user(self) -> None:
        """Step 4: JIT provisioner creates new user from OIDC claims."""
        provisioner = JitProvisioner()
        session = mock_session()

        userinfo = OidcUserInfo(
            sub="newuser123",
            email="new@company.com",
            name="New User",
        )

        new_user = _make_user(
            rid="ri.user.new1",
            email="new@company.com",
            display_name="New User",
        )

        with (
            patch("lingshu.setting.auth.jit_provisioning.UserRepository") as MockUserRepo,
            patch("lingshu.setting.auth.jit_provisioning.MembershipRepository") as MockMemberRepo,
            patch("lingshu.setting.auth.jit_provisioning.generate_rid", return_value="ri.user.new1"),
        ):
            MockUserRepo.return_value.get_by_email = AsyncMock(return_value=None)
            MockUserRepo.return_value.create = AsyncMock(return_value=new_user)
            MockMemberRepo.return_value.create = AsyncMock()

            result = await provisioner.provision_user(
                userinfo, "ri.tenant.default", session,
            )
            assert result.email == "new@company.com"
            assert result.display_name == "New User"
            MockUserRepo.return_value.create.assert_awaited_once()
            MockMemberRepo.return_value.create.assert_awaited_once()

    async def test_step4_jit_updates_existing_user(self) -> None:
        """Step 4: JIT provisioner updates existing user's display name."""
        provisioner = JitProvisioner()
        session = mock_session()

        userinfo = OidcUserInfo(
            sub="existing123",
            email="john@company.com",
            name="John D. Updated",
        )

        existing_user = _make_user(
            rid="ri.user.sso1",
            email="john@company.com",
            display_name="John Doe",
        )
        updated_user = _make_user(
            rid="ri.user.sso1",
            email="john@company.com",
            display_name="John D. Updated",
        )

        with (
            patch("lingshu.setting.auth.jit_provisioning.UserRepository") as MockUserRepo,
            patch("lingshu.setting.auth.jit_provisioning.MembershipRepository") as MockMemberRepo,
        ):
            MockUserRepo.return_value.get_by_email = AsyncMock(
                return_value=existing_user,
            )
            MockUserRepo.return_value.update_fields = AsyncMock(
                return_value=updated_user,
            )
            MockMemberRepo.return_value.get = AsyncMock(
                return_value=_make_membership(),
            )

            result = await provisioner.provision_user(
                userinfo, "ri.tenant.default", session,
            )
            assert result.display_name == "John D. Updated"
            MockUserRepo.return_value.update_fields.assert_awaited_once()

    async def test_step5_sso_user_disabled_rejected(self) -> None:
        """Step 5 error: Disabled SSO user is rejected."""
        service = _build_service_with_sso()
        session = mock_session()

        disabled_user = _make_user(status="disabled")
        tenant = _make_tenant()

        service._oidc_provider = AsyncMock()
        service._oidc_provider.exchange_code = AsyncMock(
            return_value={"access_token": "tok"},
        )
        service._oidc_provider.get_userinfo = AsyncMock(
            return_value=OidcUserInfo(
                sub="user123",
                email="john@company.com",
                name="John Doe",
            ),
        )
        service._jit_provisioner = AsyncMock()
        service._jit_provisioner.provision_user = AsyncMock(
            return_value=disabled_user,
        )

        with (
            patch("lingshu.setting.service.TenantRepository") as MockTenantRepo,
            patch("lingshu.setting.service.MembershipRepository"),
            patch("lingshu.setting.service.RefreshTokenRepository"),
        ):
            MockTenantRepo.return_value.list_all = AsyncMock(
                return_value=([tenant], 1),
            )

            with pytest.raises(AppError) as exc_info:
                await service.sso_callback("code", "state", session)
            assert exc_info.value.code == ErrorCode.SETTING_PERMISSION_DENIED

    async def test_sso_callback_no_email(self) -> None:
        """SSO callback with no email in claims raises error."""
        service = _build_service_with_sso()
        session = mock_session()

        tenant = _make_tenant()

        service._oidc_provider = AsyncMock()
        service._oidc_provider.exchange_code = AsyncMock(
            return_value={"access_token": "tok"},
        )
        service._oidc_provider.get_userinfo = AsyncMock(
            return_value=OidcUserInfo(sub="user123", email="", name="No Email"),
        )

        with (
            patch("lingshu.setting.service.TenantRepository") as MockTenantRepo,
        ):
            MockTenantRepo.return_value.list_all = AsyncMock(
                return_value=([tenant], 1),
            )

            with pytest.raises(AppError) as exc_info:
                await service.sso_callback("code", "state", session)
            assert exc_info.value.code == ErrorCode.SETTING_AUTH_INVALID_CREDENTIALS

    async def test_sso_callback_no_tenant(self) -> None:
        """SSO callback with no available tenant raises error."""
        service = _build_service_with_sso()
        session = mock_session()

        service._oidc_provider = AsyncMock()
        service._oidc_provider.exchange_code = AsyncMock(
            return_value={"access_token": "tok"},
        )
        service._oidc_provider.get_userinfo = AsyncMock(
            return_value=OidcUserInfo(sub="user123", email="john@co.com", name="John"),
        )

        with (
            patch("lingshu.setting.service.TenantRepository") as MockTenantRepo,
        ):
            MockTenantRepo.return_value.list_all = AsyncMock(
                return_value=([], 0),
            )

            with pytest.raises(AppError) as exc_info:
                await service.sso_callback("code", "state", session)
            assert exc_info.value.code == ErrorCode.COMMON_INTERNAL_ERROR
