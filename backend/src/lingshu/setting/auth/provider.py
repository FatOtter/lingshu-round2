"""Identity Provider: JWT token issuance, validation, refresh, and revocation."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from authlib.jose import jwt as authlib_jwt
from authlib.jose.errors import ExpiredTokenError, JoseError
from redis.asyncio import Redis

from lingshu.config import Settings


class TokenPayload:
    """Parsed JWT token payload."""

    def __init__(self, claims: dict[str, Any]) -> None:
        self.sub: str = claims["sub"]
        self.tid: str = claims["tid"]
        self.role: str = claims["role"]
        self.jti: str = claims["jti"]
        self.exp: int = claims["exp"]
        self.iat: int = claims["iat"]


class IdentityProvider(Protocol):
    """Abstract identity provider interface."""

    def issue_access_token(
        self, user_rid: str, tenant_rid: str, role: str
    ) -> str: ...

    def issue_refresh_token(
        self, user_rid: str, tenant_rid: str
    ) -> tuple[str, str]: ...

    def validate_token(self, token: str) -> TokenPayload: ...

    async def revoke_token(self, jti: str, exp: int) -> None: ...

    async def is_revoked(self, tenant_id: str, jti: str) -> bool: ...


class BuiltinProvider:
    """Built-in JWT identity provider using authlib."""

    def __init__(self, settings: Settings, redis: Redis) -> None:
        self._settings = settings
        self._secret = settings.jwt_secret
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = settings.access_token_ttl
        self._refresh_ttl = settings.refresh_token_ttl
        self._redis = redis

    def issue_access_token(
        self, user_rid: str, tenant_rid: str, role: str
    ) -> str:
        now = datetime.now(UTC)
        claims = {
            "iss": "lingshu",
            "sub": user_rid,
            "aud": "lingshu",
            "tid": tenant_rid,
            "role": role,
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._access_ttl)).timestamp()),
        }
        header = {"alg": self._algorithm}
        token: bytes = authlib_jwt.encode(header, claims, self._secret)
        return token.decode("utf-8")

    def issue_refresh_token(
        self, user_rid: str, tenant_rid: str
    ) -> tuple[str, str]:
        """Issue a refresh token. Returns (raw_token, token_hash)."""
        raw_token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        return raw_token, token_hash

    def validate_token(self, token: str) -> TokenPayload:
        """Validate and decode a JWT token.

        Raises:
            ValueError: If the token is invalid or expired.
        """
        try:
            claims = authlib_jwt.decode(token, self._secret)
            claims.validate()
        except ExpiredTokenError:
            raise ValueError("Token expired") from None
        except JoseError as e:
            raise ValueError(f"Invalid token: {e}") from None

        if claims.get("iss") != "lingshu" or claims.get("aud") != "lingshu":
            raise ValueError("Invalid token issuer or audience")

        return TokenPayload(dict(claims))

    async def revoke_token(self, jti: str, exp: int) -> None:
        """Add a token to the blacklist."""
        now = int(datetime.now(UTC).timestamp())
        ttl = max(exp - now, 0)
        if ttl > 0:
            await self._redis.setex(f"jwt_blacklist:{jti}", ttl, "1")

    async def is_revoked(self, tenant_id: str, jti: str) -> bool:
        """Check if a token is in the blacklist."""
        result = await self._redis.get(f"jwt_blacklist:{jti}")
        return result is not None
