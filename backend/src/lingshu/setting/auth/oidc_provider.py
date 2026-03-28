"""External OIDC Provider for SSO authentication."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
from authlib.jose import jwt as authlib_jwt
from authlib.jose.errors import JoseError


@dataclass(frozen=True)
class OidcConfig:
    """OIDC provider configuration."""

    issuer_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str] = field(default_factory=lambda: ["openid", "profile", "email"])


@dataclass(frozen=True)
class OidcUserInfo:
    """Normalized user info from OIDC provider."""

    sub: str
    email: str
    name: str
    raw_claims: dict[str, Any] = field(default_factory=dict)


class OidcProvider:
    """External OIDC provider supporting Keycloak and generic OIDC via discovery."""

    def __init__(self, config: OidcConfig) -> None:
        self._config = config
        self._discovery: dict[str, Any] | None = None

    async def _discover(self) -> dict[str, Any]:
        """Fetch OIDC well-known configuration (cached after first call)."""
        if self._discovery is not None:
            return self._discovery

        url = f"{self._config.issuer_url.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            self._discovery = resp.json()
        return self._discovery

    async def get_authorization_url(self, state: str, nonce: str) -> str:
        """Build the IdP authorization redirect URL."""
        discovery = await self._discover()
        auth_endpoint = discovery["authorization_endpoint"]
        params = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "scope": " ".join(self._config.scopes),
            "state": state,
            "nonce": nonce,
        }
        return f"{auth_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, state: str) -> dict[str, Any]:
        """Exchange authorization code for tokens from the IdP."""
        discovery = await self._discover()
        token_endpoint = discovery["token_endpoint"]
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._config.redirect_uri,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(token_endpoint, data=payload)
            resp.raise_for_status()
            return resp.json()

    async def verify_id_token(self, id_token: str) -> dict[str, Any]:
        """Validate and decode the ID token JWT from the IdP.

        Fetches the IdP JWKS for signature verification.
        """
        discovery = await self._discover()
        jwks_uri = discovery["jwks_uri"]

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(jwks_uri)
            resp.raise_for_status()
            jwks = resp.json()

        try:
            claims = authlib_jwt.decode(id_token, jwks)
            claims.validate()
        except JoseError as e:
            raise ValueError(f"Invalid ID token: {e}") from None

        return dict(claims)

    async def get_userinfo(self, access_token: str) -> OidcUserInfo:
        """Fetch user info from the IdP userinfo endpoint."""
        discovery = await self._discover()
        userinfo_endpoint = discovery["userinfo_endpoint"]

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        return OidcUserInfo(
            sub=data["sub"],
            email=data.get("email", ""),
            name=data.get("name", data.get("preferred_username", data["sub"])),
            raw_claims=data,
        )

    @staticmethod
    def generate_state() -> str:
        """Generate a cryptographic random state parameter."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_nonce() -> str:
        """Generate a cryptographic random nonce."""
        return secrets.token_urlsafe(32)
