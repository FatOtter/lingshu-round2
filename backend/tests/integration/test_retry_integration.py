"""IT-04: Integration tests for Neo4j failure retry logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from neo4j.exceptions import ServiceUnavailable

from lingshu.ontology.retry import retry_neo4j_operation


# ── Tests ─────────────────────────────────────────────────────────


class TestRetrySucceedsAfterTransientFailure:
    """Operation should succeed after transient failure on first attempt."""

    async def test_retry_succeeds_after_transient_failure(self) -> None:
        call_count = 0

        async def flaky_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ServiceUnavailable("Connection lost")
            return "success"

        with patch("lingshu.ontology.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_neo4j_operation(
                flaky_operation,
                max_retries=3,
                base_delay=0.01,
                max_delay=0.05,
            )

        assert result == "success"
        assert call_count == 2


class TestAllRetriesExhaustedRaises:
    """Operation should raise after all retries are exhausted."""

    async def test_all_retries_exhausted_raises(self) -> None:
        call_count = 0

        async def always_failing() -> str:
            nonlocal call_count
            call_count += 1
            raise ServiceUnavailable("Neo4j is down")

        with patch("lingshu.ontology.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ServiceUnavailable, match="Neo4j is down"):
                await retry_neo4j_operation(
                    always_failing,
                    max_retries=2,
                    base_delay=0.01,
                    max_delay=0.05,
                )

        # Initial attempt + 2 retries = 3 total
        assert call_count == 3


class TestImmediateSuccessNoRetry:
    """Operation that succeeds immediately should not trigger any retries."""

    async def test_immediate_success_no_retry(self) -> None:
        call_count = 0

        async def success_operation() -> str:
            nonlocal call_count
            call_count += 1
            return "done"

        sleep_mock = AsyncMock()
        with patch("lingshu.ontology.retry.asyncio.sleep", sleep_mock):
            result = await retry_neo4j_operation(
                success_operation,
                max_retries=3,
                base_delay=0.01,
            )

        assert result == "done"
        assert call_count == 1
        sleep_mock.assert_not_awaited()


class TestRetryWithMultipleTransientFailures:
    """Operation should retry through multiple transient failures."""

    async def test_retry_with_multiple_transient_failures(self) -> None:
        call_count = 0

        async def multi_fail_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ServiceUnavailable(f"Failure {call_count}")
            return "recovered"

        with patch("lingshu.ontology.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_neo4j_operation(
                multi_fail_operation,
                max_retries=3,
                base_delay=0.01,
                max_delay=0.05,
            )

        assert result == "recovered"
        assert call_count == 4  # 3 failures + 1 success


class TestNonRetryableExceptionNotRetried:
    """Non-transient exceptions should not be retried."""

    async def test_non_retryable_exception_not_retried(self) -> None:
        call_count = 0

        async def value_error_operation() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a transient error")

        with pytest.raises(ValueError, match="Not a transient error"):
            await retry_neo4j_operation(
                value_error_operation,
                max_retries=3,
                base_delay=0.01,
            )

        # Should only be called once — no retry for ValueError
        assert call_count == 1
