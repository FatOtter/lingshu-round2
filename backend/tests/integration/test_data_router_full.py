"""Comprehensive integration tests for Data module router endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lingshu.data.router import router, set_data_service
from lingshu.data.schemas.responses import (
    BranchResponse,
    ConnectionResponse,
    ConnectionTestResponse,
    DataOverviewResponse,
    InstanceQueryResponse,
)
from lingshu.infra.errors import register_exception_handlers


# ── Helpers ────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(UTC)


def _conn(**overrides: Any) -> ConnectionResponse:
    defaults = dict(
        rid="ri.conn.1", display_name="Test DB", type="postgresql",
        config={"host": "localhost"}, status="connected",
        created_at=_now(), updated_at=_now(),
    )
    return ConnectionResponse(**(defaults | overrides))


def _branch(**overrides: Any) -> dict[str, Any]:
    defaults = dict(name="main", hash="abc123", metadata=None)
    return defaults | overrides


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def mock_svc() -> MagicMock:
    svc = MagicMock()
    svc.create_connection = AsyncMock()
    svc.query_connections = AsyncMock()
    svc.get_connection = AsyncMock()
    svc.update_connection = AsyncMock()
    svc.delete_connection = AsyncMock()
    svc.test_connection = AsyncMock()
    svc.query_instances = AsyncMock()
    svc.get_instance = AsyncMock()
    svc.get_overview = AsyncMock()
    svc.list_branches = AsyncMock()
    svc.get_branch = AsyncMock()
    svc.create_branch = AsyncMock()
    svc.delete_branch = AsyncMock()
    svc.merge_branch = AsyncMock()
    svc.diff_branches = AsyncMock()
    return svc


@pytest.fixture
def app(mock_svc: MagicMock) -> FastAPI:
    _app = FastAPI()
    register_exception_handlers(_app)
    _app.include_router(router)
    set_data_service(mock_svc)  # type: ignore[arg-type]
    return _app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _override_db(app: FastAPI) -> None:
    from lingshu.data.router import get_db

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db


@pytest.fixture(autouse=True)
def _patch_context():
    """Patch get_tenant_id for instance endpoints that call it directly."""
    with patch("lingshu.data.router.get_tenant_id", return_value="ri.tenant.t1"):
        yield


# ── Connection CRUD ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_connection(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_connection.return_value = _conn()
    r = await client.post("/data/v1/connections", json={
        "display_name": "My DB", "type": "postgresql",
        "config": {"host": "localhost", "port": 5432},
    })
    assert r.status_code == 201
    assert r.json()["data"]["rid"] == "ri.conn.1"


@pytest.mark.asyncio
async def test_query_connections(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_connections.return_value = ([_conn()], 1)
    r = await client.post("/data/v1/connections/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_query_connections_with_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_connections.return_value = ([], 0)
    r = await client.post("/data/v1/connections/query", json={
        "type": "iceberg",
        "pagination": {"page": 1, "page_size": 10},
    })
    assert r.status_code == 200
    mock_svc.query_connections.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_connection(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_connection.return_value = _conn()
    r = await client.get("/data/v1/connections/ri.conn.1")
    assert r.status_code == 200
    assert r.json()["data"]["type"] == "postgresql"


@pytest.mark.asyncio
async def test_update_connection(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_connection.return_value = _conn(display_name="Renamed")
    r = await client.put("/data/v1/connections/ri.conn.1", json={
        "display_name": "Renamed",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_connection(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/data/v1/connections/ri.conn.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Connection deleted"


@pytest.mark.asyncio
async def test_test_connection(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.test_connection.return_value = ConnectionTestResponse(
        success=True, latency_ms=15.2, server_version="16.1",
    )
    r = await client.post("/data/v1/connections/ri.conn.1/test")
    assert r.status_code == 200
    assert r.json()["data"]["success"] is True


# ── Instance Query ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_object_instances(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_instances.return_value = {
        "rows": [{"id": 1, "name": "Alice"}], "total": 1,
        "columns": ["id", "name"], "schema_info": None,
    }
    r = await client.post("/data/v1/objects/ri.obj.1/instances/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_get_object_instance(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_instance.return_value = {"id": 1, "name": "Alice"}
    r = await client.post("/data/v1/objects/ri.obj.1/instances/get", json={
        "primary_key": {"id": 1},
    })
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Alice"


@pytest.mark.asyncio
async def test_get_object_instance_not_found(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_instance.return_value = None
    r = await client.post("/data/v1/objects/ri.obj.1/instances/get", json={
        "primary_key": {"id": 999},
    })
    assert r.status_code == 200
    assert r.json()["data"] == {}


@pytest.mark.asyncio
async def test_query_link_instances(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_instances.return_value = {
        "rows": [], "total": 0, "columns": [], "schema_info": None,
    }
    r = await client.post("/data/v1/links/ri.link.1/instances/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_get_link_instance(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_instance.return_value = {"source": "a", "target": "b"}
    r = await client.post("/data/v1/links/ri.link.1/instances/get", json={
        "primary_key": {"source": "a", "target": "b"},
    })
    assert r.status_code == 200


# ── Overview ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_data_overview(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_overview.return_value = {"connections": {"total": 3, "connected": 2}}
    r = await client.get("/data/v1/overview")
    assert r.status_code == 200
    assert r.json()["data"]["connections"]["total"] == 3


# ── Branch Management ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_branches(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.list_branches.return_value = [_branch(), _branch(name="dev", hash="def456")]
    r = await client.get("/data/v1/branches")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 2


@pytest.mark.asyncio
async def test_get_branch(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_branch.return_value = _branch()
    r = await client.get("/data/v1/branches/main")
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "main"


@pytest.mark.asyncio
async def test_create_branch(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_branch.return_value = _branch(name="feature1", hash="xyz789")
    r = await client.post("/data/v1/branches", json={
        "name": "feature1", "from_ref": "main",
    })
    assert r.status_code == 201
    assert r.json()["data"]["name"] == "feature1"


@pytest.mark.asyncio
async def test_delete_branch(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/data/v1/branches/feature1")
    assert r.status_code == 200
    assert "deleted" in r.json()["data"]["message"]


@pytest.mark.asyncio
async def test_merge_branch(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.merge_branch.return_value = {"merged": True, "conflicts": 0}
    r = await client.post("/data/v1/branches/feature1/merge", json={"target": "main"})
    assert r.status_code == 200
    assert r.json()["data"]["merged"] is True


@pytest.mark.asyncio
async def test_diff_branches(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.diff_branches.return_value = [{"type": "added", "path": "/table1/row1"}]
    r = await client.get("/data/v1/branches/main/diff/feature1")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1
