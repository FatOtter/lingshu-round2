"""Redis async connection management."""

from redis.asyncio import Redis

_redis: Redis | None = None


async def init_redis(redis_url: str) -> None:
    """Initialize Redis async connection."""
    global _redis
    _redis = Redis.from_url(redis_url, decode_responses=True)
    await _redis.ping()  # type: ignore[misc]


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis() -> Redis:
    """Return the current Redis client."""
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis
