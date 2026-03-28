"""Refresh token repository: create, revoke, cleanup."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.setting.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, token: RefreshToken) -> RefreshToken:
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token_hash: str) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked_at=datetime.utcnow())
        )
        await self._session.flush()

    async def revoke_all_for_user(self, user_rid: str, tenant_rid: str) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_rid == user_rid,
                RefreshToken.tenant_rid == tenant_rid,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.utcnow())
        )
        await self._session.flush()

    def is_valid(self, token: RefreshToken) -> bool:
        return token.revoked_at is None and token.expires_at > datetime.utcnow()
