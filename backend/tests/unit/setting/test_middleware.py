"""Tests for Auth Middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from lingshu.setting.auth.provider import BuiltinProvider


def _create_test_app(provider: BuiltinProvider, dev_mode: bool = False):
    """Create a minimal app with auth middleware for testing."""
    from fastapi import FastAPI

    from lingshu.infra.errors import register_exception_handlers
    from lingshu.setting.auth.middleware import AuthMiddleware

    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(AuthMiddleware, dev_mode=dev_mode)

    # Set auth_provider on app.state so middleware can resolve it lazily
    app.state.auth_provider = provider

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected():
        from lingshu.infra.context import get_tenant_id, get_user_id
        return {"user": get_user_id(), "tenant": get_tenant_id()}

    return app


@pytest.fixture
def mock_provider():
    p = MagicMock(spec=BuiltinProvider)
    p.validate_token = MagicMock()
    p.is_revoked = AsyncMock(return_value=False)
    return p


class TestWhitelist:
    @pytest.mark.asyncio
    async def test_health_bypasses_auth(self, mock_provider):
        app = _create_test_app(mock_provider)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_requires_auth(self, mock_provider):
        app = _create_test_app(mock_provider)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/protected")
        assert response.status_code == 401


class TestCookieAuth:
    @pytest.mark.asyncio
    async def test_valid_cookie(self, mock_provider):
        payload = MagicMock()
        payload.sub = "ri.user.test"
        payload.tid = "ri.tenant.test"
        payload.role = "admin"
        payload.jti = "jti-123"
        mock_provider.validate_token.return_value = payload

        app = _create_test_app(mock_provider)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/protected",
                cookies={"lingshu_access": "valid-token"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["user"] == "ri.user.test"
        assert data["tenant"] == "ri.tenant.test"

    @pytest.mark.asyncio
    async def test_expired_cookie(self, mock_provider):
        mock_provider.validate_token.side_effect = ValueError("Token expired")
        app = _create_test_app(mock_provider)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/protected",
                cookies={"lingshu_access": "expired-token"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_revoked_cookie(self, mock_provider):
        payload = MagicMock()
        payload.sub = "ri.user.test"
        payload.tid = "ri.tenant.test"
        payload.role = "admin"
        payload.jti = "jti-revoked"
        mock_provider.validate_token.return_value = payload
        mock_provider.is_revoked = AsyncMock(return_value=True)

        app = _create_test_app(mock_provider)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/protected",
                cookies={"lingshu_access": "revoked-token"},
            )
        assert response.status_code == 401


class TestDevMode:
    @pytest.mark.asyncio
    async def test_header_auth_in_dev(self, mock_provider):
        app = _create_test_app(mock_provider, dev_mode=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/protected",
                headers={
                    "X-User-ID": "ri.user.dev",
                    "X-Tenant-ID": "ri.tenant.dev",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["user"] == "ri.user.dev"

    @pytest.mark.asyncio
    async def test_missing_headers_in_dev(self, mock_provider):
        app = _create_test_app(mock_provider, dev_mode=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/protected")
        assert response.status_code == 401
