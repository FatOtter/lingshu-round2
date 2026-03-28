"""Tests for SSO: OIDC provider, JIT provisioning, and SSO callback flow."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.setting.auth.jit_provisioning import JitProvisioner
from lingshu.setting.auth.oidc_provider import OidcConfig, OidcProvider, OidcUserInfo


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def oidc_config():
    return OidcConfig(
        issuer_url="https://idp.example.com/realms/test",
        client_id="lingshu-client",
        client_secret="super-secret",
        redirect_uri="http://localhost:3000/sso/callback",
    )


@pytest.fixture
def oidc_provider(oidc_config):
    return OidcProvider(oidc_config)


DISCOVERY_DOC = {
    "authorization_endpoint": "https://idp.example.com/realms/test/protocol/openid-connect/auth",
    "token_endpoint": "https://idp.example.com/realms/test/protocol/openid-connect/token",
    "userinfo_endpoint": "https://idp.example.com/realms/test/protocol/openid-connect/userinfo",
    "jwks_uri": "https://idp.example.com/realms/test/protocol/openid-connect/certs",
}


def _mock_httpx_get(url, **kwargs):
    """Return mock responses for OIDC discovery and userinfo."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if ".well-known" in url:
        resp.json.return_value = DISCOVERY_DOC
    elif "userinfo" in url:
        resp.json.return_value = {
            "sub": "oidc-user-123",
            "email": "jane@example.com",
            "name": "Jane Doe",
        }
    elif "certs" in url:
        resp.json.return_value = {"keys": []}
    return resp


def _mock_httpx_post(url, **kwargs):
    """Return mock response for token exchange."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "access_token": "idp-access-token-abc",
        "id_token": "idp-id-token-xyz",
        "token_type": "Bearer",
        "expires_in": 300,
    }
    return resp


# ── OidcProvider Tests ──────────────────────────────────────────


class TestAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_generates_valid_authorization_url(self, oidc_provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_mock_httpx_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lingshu.setting.auth.oidc_provider.httpx.AsyncClient", return_value=mock_client):
            url = await oidc_provider.get_authorization_url("test-state", "test-nonce")

        assert "authorization_endpoint" not in url  # Should be resolved
        assert "response_type=code" in url
        assert "client_id=lingshu-client" in url
        assert "state=test-state" in url
        assert "nonce=test-nonce" in url
        assert url.startswith("https://idp.example.com/realms/test/protocol/openid-connect/auth")

    @pytest.mark.asyncio
    async def test_includes_scopes(self, oidc_provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_mock_httpx_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lingshu.setting.auth.oidc_provider.httpx.AsyncClient", return_value=mock_client):
            url = await oidc_provider.get_authorization_url("s", "n")

        assert "scope=openid+profile+email" in url or "scope=openid" in url


class TestCodeExchange:
    @pytest.mark.asyncio
    async def test_exchanges_code_for_tokens(self, oidc_provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_mock_httpx_get)
        mock_client.post = AsyncMock(side_effect=_mock_httpx_post)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lingshu.setting.auth.oidc_provider.httpx.AsyncClient", return_value=mock_client):
            # Pre-populate discovery cache
            await oidc_provider.get_authorization_url("s", "n")
            tokens = await oidc_provider.exchange_code("auth-code-123", "test-state")

        assert tokens["access_token"] == "idp-access-token-abc"
        assert tokens["id_token"] == "idp-id-token-xyz"

    @pytest.mark.asyncio
    async def test_exchange_calls_token_endpoint(self, oidc_provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_mock_httpx_get)
        mock_client.post = AsyncMock(side_effect=_mock_httpx_post)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lingshu.setting.auth.oidc_provider.httpx.AsyncClient", return_value=mock_client):
            await oidc_provider.get_authorization_url("s", "n")
            await oidc_provider.exchange_code("code", "state")

        # Verify post was called with the token endpoint
        post_calls = [c for c in mock_client.post.call_args_list]
        assert len(post_calls) == 1
        assert "token" in post_calls[0].args[0]


class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_fetches_userinfo(self, oidc_provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_mock_httpx_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("lingshu.setting.auth.oidc_provider.httpx.AsyncClient", return_value=mock_client):
            await oidc_provider.get_authorization_url("s", "n")
            userinfo = await oidc_provider.get_userinfo("access-token")

        assert userinfo.sub == "oidc-user-123"
        assert userinfo.email == "jane@example.com"
        assert userinfo.name == "Jane Doe"


class TestStateAndNonce:
    def test_generate_state_is_unique(self):
        s1 = OidcProvider.generate_state()
        s2 = OidcProvider.generate_state()
        assert s1 != s2
        assert len(s1) > 20

    def test_generate_nonce_is_unique(self):
        n1 = OidcProvider.generate_nonce()
        n2 = OidcProvider.generate_nonce()
        assert n1 != n2


# ── JIT Provisioning Tests ──────────────────────────────────────


class TestJitProvisionNewUser:
    @pytest.mark.asyncio
    async def test_creates_new_user(self):
        provisioner = JitProvisioner()
        userinfo = OidcUserInfo(
            sub="oidc-new-user",
            email="newuser@example.com",
            name="New User",
        )

        mock_session = AsyncMock()
        mock_user_repo = MagicMock()
        mock_membership_repo = MagicMock()

        # User does not exist
        mock_user_repo.get_by_email = AsyncMock(return_value=None)
        created_user = MagicMock()
        created_user.rid = "ri.user.new-uuid"
        created_user.email = "newuser@example.com"
        created_user.display_name = "New User"
        created_user.status = "active"
        created_user.created_at = datetime.now()
        created_user.updated_at = datetime.now()
        mock_user_repo.create = AsyncMock(return_value=created_user)
        mock_membership_repo.create = AsyncMock()

        with (
            patch("lingshu.setting.auth.jit_provisioning.UserRepository", return_value=mock_user_repo),
            patch("lingshu.setting.auth.jit_provisioning.MembershipRepository", return_value=mock_membership_repo),
        ):
            user = await provisioner.provision_user(userinfo, "ri.tenant.default", mock_session)

        assert user.email == "newuser@example.com"
        assert user.display_name == "New User"
        mock_user_repo.create.assert_called_once()
        mock_membership_repo.create.assert_called_once()


class TestJitProvisionExistingUser:
    @pytest.mark.asyncio
    async def test_updates_display_name(self):
        provisioner = JitProvisioner()
        userinfo = OidcUserInfo(
            sub="oidc-existing",
            email="existing@example.com",
            name="Updated Name",
        )

        mock_session = AsyncMock()
        mock_user_repo = MagicMock()
        mock_membership_repo = MagicMock()

        existing_user = MagicMock()
        existing_user.rid = "ri.user.existing"
        existing_user.email = "existing@example.com"
        existing_user.display_name = "Old Name"
        existing_user.status = "active"

        updated_user = MagicMock()
        updated_user.rid = "ri.user.existing"
        updated_user.email = "existing@example.com"
        updated_user.display_name = "Updated Name"

        mock_user_repo.get_by_email = AsyncMock(return_value=existing_user)
        mock_user_repo.update_fields = AsyncMock(return_value=updated_user)
        mock_membership_repo.get = AsyncMock(return_value=MagicMock())  # Already a member

        with (
            patch("lingshu.setting.auth.jit_provisioning.UserRepository", return_value=mock_user_repo),
            patch("lingshu.setting.auth.jit_provisioning.MembershipRepository", return_value=mock_membership_repo),
        ):
            user = await provisioner.provision_user(userinfo, "ri.tenant.default", mock_session)

        assert user.display_name == "Updated Name"
        mock_user_repo.update_fields.assert_called_once_with("ri.user.existing", display_name="Updated Name")
        # Should NOT create a new user
        mock_user_repo.create.assert_not_called()


class TestJitProvisionExistingUserNewTenant:
    @pytest.mark.asyncio
    async def test_creates_membership_for_new_tenant(self):
        provisioner = JitProvisioner()
        userinfo = OidcUserInfo(
            sub="oidc-existing",
            email="existing@example.com",
            name="Same Name",
        )

        mock_session = AsyncMock()
        mock_user_repo = MagicMock()
        mock_membership_repo = MagicMock()

        existing_user = MagicMock()
        existing_user.rid = "ri.user.existing"
        existing_user.email = "existing@example.com"
        existing_user.display_name = "Same Name"  # Same name, no update needed

        mock_user_repo.get_by_email = AsyncMock(return_value=existing_user)
        mock_membership_repo.get = AsyncMock(return_value=None)  # Not a member of this tenant
        mock_membership_repo.create = AsyncMock()

        with (
            patch("lingshu.setting.auth.jit_provisioning.UserRepository", return_value=mock_user_repo),
            patch("lingshu.setting.auth.jit_provisioning.MembershipRepository", return_value=mock_membership_repo),
        ):
            await provisioner.provision_user(userinfo, "ri.tenant.new", mock_session)

        mock_membership_repo.create.assert_called_once()
        mock_user_repo.update_fields.assert_not_called()


# ── SSO Config Tests ─────────────────────────────────────────────


class TestSsoConfig:
    def test_sso_disabled_when_no_config(self):
        from lingshu.setting.service import SettingServiceImpl

        svc = SettingServiceImpl(
            provider=MagicMock(),
            enforcer=MagicMock(),
            settings=None,
        )
        config = svc.get_sso_config()
        assert config.enabled is False
        assert config.provider_name is None

    def test_sso_enabled_when_configured(self):
        from lingshu.setting.service import SettingServiceImpl

        mock_settings = MagicMock()
        mock_settings.sso_enabled = True
        mock_settings.oidc_issuer_url = "https://idp.example.com"
        mock_settings.oidc_client_id = "client-id"
        mock_settings.oidc_client_secret = "secret"
        mock_settings.oidc_redirect_uri = "http://localhost:3000/sso/callback"
        mock_settings.oidc_provider_name = "Keycloak"

        svc = SettingServiceImpl(
            provider=MagicMock(),
            enforcer=MagicMock(),
            settings=mock_settings,
        )
        config = svc.get_sso_config()
        assert config.enabled is True
        assert config.provider_name == "Keycloak"
