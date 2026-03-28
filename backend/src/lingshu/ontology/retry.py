"""Retry logic for Neo4j transient failures."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Exceptions considered transient and safe to retry
RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ServiceUnavailable,
    SessionExpired,
    TransientError,
)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 0.5  # seconds
DEFAULT_MAX_DELAY = 5.0  # seconds


async def retry_neo4j_operation(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> T:
    """Execute an async operation with exponential backoff retry on Neo4j transient errors.

    Args:
        operation: Async callable to execute.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay in seconds between retries.

    Returns:
        The result of the operation.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exception: BaseException | None = None

    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except RETRYABLE_EXCEPTIONS as exc:
            last_exception = exc
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "Neo4j transient error (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    max_retries + 1,
                    delay,
                    str(exc),
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Neo4j operation failed after %d attempts: %s",
                    max_retries + 1,
                    str(exc),
                )

    # Should not reach here, but satisfy type checker
    raise last_exception  # type: ignore[misc]
