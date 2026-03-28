"""Row-level optimistic locking using Redis."""

from __future__ import annotations

import hashlib
import json

from redis.asyncio import Redis


class RowLock:
    """Row-level optimistic locking using Redis.

    Each lock is identified by (tenant_id, type_rid, primary_key) and stored
    as a Redis key with the *user_id* as the value.  The TTL prevents stale
    locks from persisting indefinitely.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def acquire(
        self,
        tenant_id: str,
        type_rid: str,
        primary_key: dict[str, object],
        user_id: str,
        ttl: int = 300,
    ) -> bool:
        """Try to acquire a lock on a specific row.

        Returns ``True`` if the lock was acquired (or already held by the same
        user), ``False`` otherwise.
        """
        key = self._make_key(tenant_id, type_rid, primary_key)

        # Try to set if not exists
        acquired = await self._redis.set(key, user_id, nx=True, ex=ttl)
        if acquired:
            return True

        # If already held by the same user, refresh TTL
        current_holder = await self._redis.get(key)
        if current_holder == user_id:
            await self._redis.expire(key, ttl)
            return True

        return False

    async def release(
        self,
        tenant_id: str,
        type_rid: str,
        primary_key: dict[str, object],
        user_id: str,
    ) -> bool:
        """Release a lock.  Only succeeds if held by the same user."""
        key = self._make_key(tenant_id, type_rid, primary_key)
        current_holder = await self._redis.get(key)
        if current_holder != user_id:
            return False
        await self._redis.delete(key)
        return True

    async def is_locked(
        self,
        tenant_id: str,
        type_rid: str,
        primary_key: dict[str, object],
    ) -> tuple[bool, str | None]:
        """Check if a row is locked.

        Returns ``(is_locked, holder_user_id)``.
        """
        key = self._make_key(tenant_id, type_rid, primary_key)
        holder = await self._redis.get(key)
        if holder is None:
            return False, None
        return True, str(holder)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _make_key(
        tenant_id: str,
        type_rid: str,
        primary_key: dict[str, object],
    ) -> str:
        """Generate a deterministic Redis key for the row lock."""
        pk_hash = hashlib.sha256(
            json.dumps(primary_key, sort_keys=True).encode()
        ).hexdigest()[:16]
        return f"row_lock:{tenant_id}:{type_rid}:{pk_hash}"
