"""Unit tests for T4: Neo4j failure retry logic."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from lingshu.ontology.retry import (
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_RETRIES,
    retry_neo4j_operation,
)


class TestRetryNeo4jOperation:
    """Tests for retry_neo4j_operation."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self) -> None:
        """Operation succeeds immediately without retry."""
        op = AsyncMock(return_value="success")
        result = await retry_neo4j_operation(op)
        assert result == "success"
        assert op.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_service_unavailable(self) -> None:
        """Retries on ServiceUnavailable then succeeds."""
        op = AsyncMock(side_effect=[ServiceUnavailable("down"), "recovered"])
        with patch("lingshu.ontology.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_neo4j_operation(op, base_delay=0.01)
        assert result == "recovered"
        assert op.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_session_expired(self) -> None:
        """Retries on SessionExpired then succeeds."""
        op = AsyncMock(side_effect=[SessionExpired("expired"), "ok"])
        with patch("lingshu.ontology.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_neo4j_operation(op, base_delay=0.01)
        assert result == "ok"
        assert op.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self) -> None:
        """Retries on TransientError then succeeds."""
        op = AsyncMock(side_effect=[TransientError("transient"), "ok"])
        with patch("lingshu.ontology.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_neo4j_operation(op, base_delay=0.01)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_exhausts_retries_then_raises(self) -> None:
        """Raises after all retries exhausted."""
        error = ServiceUnavailable("persistent failure")
        op = AsyncMock(side_effect=error)
        with patch("lingshu.ontology.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ServiceUnavailable, match="persistent failure"):
                await retry_neo4j_operation(op, max_retries=2, base_delay=0.01)
        assert op.call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_non_retryable_error_not_retried(self) -> None:
        """Non-retryable errors should propagate immediately."""
        op = AsyncMock(side_effect=ValueError("bad value"))
        with pytest.raises(ValueError, match="bad value"):
            await retry_neo4j_operation(op)
        assert op.call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self) -> None:
        """Verify exponential backoff delay calculation."""
        op = AsyncMock(
            side_effect=[
                ServiceUnavailable("1"),
                ServiceUnavailable("2"),
                "success",
            ]
        )
        sleep_mock = AsyncMock()
        with patch("lingshu.ontology.retry.asyncio.sleep", sleep_mock):
            await retry_neo4j_operation(op, base_delay=1.0, max_delay=10.0)

        assert sleep_mock.call_count == 2
        # First delay: 1.0 * 2^0 = 1.0
        assert sleep_mock.call_args_list[0][0][0] == 1.0
        # Second delay: 1.0 * 2^1 = 2.0
        assert sleep_mock.call_args_list[1][0][0] == 2.0

    @pytest.mark.asyncio
    async def test_max_delay_cap(self) -> None:
        """Delay should be capped at max_delay."""
        op = AsyncMock(
            side_effect=[
                ServiceUnavailable("1"),
                ServiceUnavailable("2"),
                ServiceUnavailable("3"),
                "ok",
            ]
        )
        sleep_mock = AsyncMock()
        with patch("lingshu.ontology.retry.asyncio.sleep", sleep_mock):
            await retry_neo4j_operation(
                op, base_delay=1.0, max_delay=2.5, max_retries=3,
            )

        # Third delay: min(1.0 * 2^2, 2.5) = 2.5
        assert sleep_mock.call_args_list[2][0][0] == 2.5

    @pytest.mark.asyncio
    async def test_zero_retries(self) -> None:
        """With max_retries=0, should not retry at all."""
        op = AsyncMock(side_effect=ServiceUnavailable("fail"))
        with pytest.raises(ServiceUnavailable):
            await retry_neo4j_operation(op, max_retries=0)
        assert op.call_count == 1
