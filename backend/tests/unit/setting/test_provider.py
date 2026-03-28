"""Tests for JWT identity provider."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.setting.auth.provider import BuiltinProvider


@pytest.fixture
def settings():
    s = MagicMock()
    s.jwt_secret = "test-secret-key-for-testing-purposes"
    s.jwt_algorithm = "HS256"
    s.access_token_ttl = 900
    s.refresh_token_ttl = 604800
    return s


@pytest.fixture
def redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    return r


@pytest.fixture
def provider(settings, redis):
    return BuiltinProvider(settings, redis)


class TestIssueAccessToken:
    def test_returns_jwt_string(self, provider):
        token = provider.issue_access_token("ri.user.123", "ri.tenant.456", "admin")
        assert isinstance(token, str)
        assert len(token) > 50

    def test_token_is_valid(self, provider):
        token = provider.issue_access_token("ri.user.123", "ri.tenant.456", "admin")
        payload = provider.validate_token(token)
        assert payload.sub == "ri.user.123"
        assert payload.tid == "ri.tenant.456"
        assert payload.role == "admin"
        assert payload.jti is not None


class TestValidateToken:
    def test_valid_token(self, provider):
        token = provider.issue_access_token("ri.user.abc", "ri.tenant.def", "member")
        payload = provider.validate_token(token)
        assert payload.sub == "ri.user.abc"

    def test_invalid_token(self, provider):
        with pytest.raises(ValueError, match="Invalid token"):
            provider.validate_token("invalid.token.here")

    def test_expired_token(self, settings, redis):
        settings.access_token_ttl = -1  # Already expired
        p = BuiltinProvider(settings, redis)
        token = p.issue_access_token("ri.user.x", "ri.tenant.y", "admin")
        with pytest.raises(ValueError, match="expired"):
            p.validate_token(token)


class TestIssueRefreshToken:
    def test_returns_raw_and_hash(self, provider):
        raw, h = provider.issue_refresh_token("ri.user.123", "ri.tenant.456")
        assert isinstance(raw, str)
        assert isinstance(h, str)
        assert raw != h
        assert len(h) == 64  # SHA-256 hex


class TestRevokeToken:
    @pytest.mark.asyncio
    async def test_revoke_adds_to_blacklist(self, provider, redis):
        future_exp = int(time.time()) + 300
        await provider.revoke_token("jti-123", future_exp)
        redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_revoked_false_by_default(self, provider, redis):
        result = await provider.is_revoked("tenant", "jti-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_revoked_true_when_in_blacklist(self, provider, redis):
        redis.get = AsyncMock(return_value="1")
        result = await provider.is_revoked("tenant", "jti-123")
        assert result is True
