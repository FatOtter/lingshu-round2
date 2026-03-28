"""Tests for health check endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from lingshu.main import create_app


@pytest.fixture
def app():
    """Create app without lifespan (skip DB connections for unit tests)."""
    return create_app()


@pytest.mark.asyncio
async def test_health_check(app):
    """Health endpoint returns ok status."""
    transport = ASGITransport(app=app)
    with (
        patch("lingshu.main.init_db", new_callable=AsyncMock),
        patch("lingshu.main.init_graph_db", new_callable=AsyncMock),
        patch("lingshu.main.init_redis", new_callable=AsyncMock),
        patch("lingshu.main.close_db", new_callable=AsyncMock),
        patch("lingshu.main.close_graph_db", new_callable=AsyncMock),
        patch("lingshu.main.close_redis", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
