"""Comprehensive integration tests for Ontology module router endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lingshu.infra.errors import register_exception_handlers
from lingshu.ontology.router import router, set_ontology_service
from lingshu.ontology.schemas.responses import (
    DraftsSummaryResponse,
    EntityResponse,
    LockStatusResponse,
    PropertyTypeResponse,
    SearchResultResponse,
    SnapshotDiffResponse,
    SnapshotResponse,
    StagingSummaryResponse,
    TopologyResponse,
)


# ── Helpers ────────────────────────────────────────────────────────

def _entity(**overrides: Any) -> EntityResponse:
    defaults = dict(
        rid="ri.obj.1", api_name="test_obj", display_name="Test Object",
        description="desc", lifecycle_status="ACTIVE", version_status="active",
        is_active=True, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
    )
    return EntityResponse(**(defaults | overrides))


def _prop(**overrides: Any) -> PropertyTypeResponse:
    defaults = dict(
        rid="ri.prop.1", api_name="test_prop", display_name="Test Prop",
        data_type="DT_STRING",
    )
    return PropertyTypeResponse(**(defaults | overrides))


def _snapshot(**overrides: Any) -> SnapshotResponse:
    defaults = dict(
        snapshot_id="ri.snap.1", parent_snapshot_id=None, tenant_id="t1",
        commit_message="Initial commit", author="admin",
        entity_changes={}, created_at="2026-01-01T00:00:00Z",
    )
    return SnapshotResponse(**(defaults | overrides))


def _lock(**overrides: Any) -> LockStatusResponse:
    defaults = dict(rid="ri.obj.1", locked=True, locked_by="user1", expires_in=300)
    return LockStatusResponse(**(defaults | overrides))


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def mock_svc() -> MagicMock:
    svc = MagicMock()
    # Entity CRUD
    svc.create_object_type = AsyncMock()
    svc.update_object_type = AsyncMock()
    svc.delete_object_type = AsyncMock()
    svc.create_link_type = AsyncMock()
    svc.update_link_type = AsyncMock()
    svc.delete_link_type = AsyncMock()
    svc.create_interface_type = AsyncMock()
    svc.update_interface_type = AsyncMock()
    svc.delete_interface_type = AsyncMock()
    svc.create_shared_property_type = AsyncMock()
    svc.update_shared_property_type = AsyncMock()
    svc.delete_shared_property_type = AsyncMock()
    svc.create_action_type = AsyncMock()
    svc.update_action_type = AsyncMock()
    svc.delete_action_type = AsyncMock()
    # Shared entity routes
    svc._query_entities = AsyncMock()
    svc._get_entity = AsyncMock()
    svc._get_entity_draft = AsyncMock()
    svc.acquire_lock = AsyncMock()
    svc.refresh_lock = AsyncMock()
    svc.release_lock = AsyncMock()
    svc.submit_to_staging = AsyncMock()
    svc.discard_draft = AsyncMock()
    svc.discard_staging = AsyncMock()
    svc.get_related = AsyncMock()
    # PropertyType
    svc.create_property_type = AsyncMock()
    svc.query_all_property_types = AsyncMock()
    # AssetMapping
    svc.query_all_asset_mappings = AsyncMock()
    svc.query_asset_mapping_references = AsyncMock()
    # Versioning
    svc.get_staging_summary = AsyncMock()
    svc.commit_staging = AsyncMock()
    svc.discard_all_staging = AsyncMock()
    svc.get_drafts_summary = AsyncMock()
    # Snapshots
    svc.query_snapshots = AsyncMock()
    svc.get_snapshot = AsyncMock()
    svc.get_snapshot_diff = AsyncMock()
    svc.rollback_to_snapshot = AsyncMock()
    # Topology & Search
    svc.get_topology = AsyncMock()
    svc.search = AsyncMock()
    return svc


@pytest.fixture
def app(mock_svc: MagicMock) -> FastAPI:
    _app = FastAPI()
    register_exception_handlers(_app)
    _app.include_router(router)
    set_ontology_service(mock_svc)  # type: ignore[arg-type]
    return _app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _override_db(app: FastAPI) -> None:
    from lingshu.ontology.router import get_db

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db


# ── ObjectType CRUD ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_object_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_object_type.return_value = _entity()
    r = await client.post("/ontology/v1/object-types", json={
        "api_name": "person", "display_name": "Person",
    })
    assert r.status_code == 201
    assert r.json()["data"]["api_name"] == "test_obj"


@pytest.mark.asyncio
async def test_update_object_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_object_type.return_value = _entity(display_name="Updated")
    r = await client.put("/ontology/v1/object-types/ri.obj.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_object_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/ontology/v1/object-types/ri.obj.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Marked for deletion"


# ── LinkType CRUD ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_link_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_link_type.return_value = _entity(rid="ri.link.1", api_name="has_parent")
    r = await client.post("/ontology/v1/link-types", json={
        "api_name": "has_parent", "display_name": "Has Parent",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_update_link_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_link_type.return_value = _entity(rid="ri.link.1")
    r = await client.put("/ontology/v1/link-types/ri.link.1", json={
        "display_name": "Updated Link",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_link_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/ontology/v1/link-types/ri.link.1")
    assert r.status_code == 200


# ── InterfaceType CRUD ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_interface_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_interface_type.return_value = _entity(rid="ri.iface.1")
    r = await client.post("/ontology/v1/interface-types", json={
        "api_name": "auditable", "display_name": "Auditable", "category": "OBJECT_INTERFACE",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_update_interface_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_interface_type.return_value = _entity(rid="ri.iface.1")
    r = await client.put("/ontology/v1/interface-types/ri.iface.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_interface_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/ontology/v1/interface-types/ri.iface.1")
    assert r.status_code == 200


# ── SharedPropertyType CRUD ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_shared_property_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_shared_property_type.return_value = _entity(rid="ri.shprop.1")
    r = await client.post("/ontology/v1/shared-property-types", json={
        "api_name": "email", "display_name": "Email", "data_type": "DT_STRING",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_update_shared_property_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_shared_property_type.return_value = _entity(rid="ri.shprop.1")
    r = await client.put("/ontology/v1/shared-property-types/ri.shprop.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_shared_property_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/ontology/v1/shared-property-types/ri.shprop.1")
    assert r.status_code == 200


# ── ActionType CRUD ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_action_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_action_type.return_value = _entity(rid="ri.action.1")
    r = await client.post("/ontology/v1/action-types", json={
        "api_name": "send_email", "display_name": "Send Email",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_update_action_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_action_type.return_value = _entity(rid="ri.action.1")
    r = await client.put("/ontology/v1/action-types/ri.action.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_action_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/ontology/v1/action-types/ri.action.1")
    assert r.status_code == 200


# ── Shared entity routes (query, get, draft, lock, staging) ───────

@pytest.mark.asyncio
async def test_query_object_types(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc._query_entities.return_value = ([_entity()], 1)
    r = await client.post("/ontology/v1/object-types/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_entity(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc._get_entity.return_value = _entity()
    r = await client.get("/ontology/v1/object-types/ri.obj.1")
    assert r.status_code == 200
    assert r.json()["data"]["rid"] == "ri.obj.1"


@pytest.mark.asyncio
async def test_get_entity_draft(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc._get_entity_draft.return_value = _entity(version_status="draft")
    r = await client.get("/ontology/v1/object-types/ri.obj.1/draft")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_lock_entity(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.acquire_lock.return_value = _lock()
    r = await client.post("/ontology/v1/object-types/ri.obj.1/lock")
    assert r.status_code == 200
    assert r.json()["data"]["locked"] is True


@pytest.mark.asyncio
async def test_heartbeat_lock(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.refresh_lock.return_value = _lock()
    r = await client.put("/ontology/v1/object-types/ri.obj.1/lock")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_unlock_entity(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.release_lock.return_value = _lock(locked=False, locked_by=None, expires_in=None)
    r = await client.delete("/ontology/v1/object-types/ri.obj.1/lock")
    assert r.status_code == 200
    assert r.json()["data"]["locked"] is False


@pytest.mark.asyncio
async def test_submit_to_staging(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.submit_to_staging.return_value = _entity(version_status="staging")
    r = await client.post("/ontology/v1/object-types/ri.obj.1/submit-to-staging")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_discard_draft(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/ontology/v1/object-types/ri.obj.1/draft")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Draft discarded"


@pytest.mark.asyncio
async def test_discard_staging(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/ontology/v1/object-types/ri.obj.1/staging")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Staging discarded"


@pytest.mark.asyncio
async def test_get_related(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_related.return_value = [{"rid": "ri.link.1", "type": "LinkType"}]
    r = await client.get("/ontology/v1/object-types/ri.obj.1/related")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


# ── PropertyType ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_object_property_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_property_type.return_value = _prop()
    r = await client.post("/ontology/v1/object-types/ri.obj.1/property-types", json={
        "api_name": "name", "display_name": "Name", "data_type": "DT_STRING",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_create_link_property_type(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_property_type.return_value = _prop()
    r = await client.post("/ontology/v1/link-types/ri.link.1/property-types", json={
        "api_name": "weight", "display_name": "Weight", "data_type": "DT_DOUBLE",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_query_all_property_types(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_all_property_types.return_value = ([_prop()], 1)
    r = await client.post("/ontology/v1/property-types/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


# ── AssetMapping ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_all_asset_mappings(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_all_asset_mappings.return_value = ([{"rid": "ri.obj.1", "mapping": {}}], 1)
    r = await client.post("/ontology/v1/asset-mappings/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_query_asset_mapping_references(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_asset_mapping_references.return_value = [{"ref": "table1"}]
    r = await client.get("/ontology/v1/asset-mappings/references?entity_rid=ri.obj.1")
    assert r.status_code == 200


# ── Version Management ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_staging_summary(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_staging_summary.return_value = StagingSummaryResponse(
        counts={"ObjectType": 2}, total=2,
    )
    r = await client.get("/ontology/v1/staging/summary")
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 2


@pytest.mark.asyncio
async def test_commit_staging(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.commit_staging.return_value = _snapshot()
    r = await client.post("/ontology/v1/staging/commit", json={"commit_message": "v1"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_discard_all_staging(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.discard_all_staging.return_value = 3
    r = await client.post("/ontology/v1/staging/discard")
    assert r.status_code == 200
    assert r.json()["data"]["discarded"] == 3


@pytest.mark.asyncio
async def test_drafts_summary(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_drafts_summary.return_value = DraftsSummaryResponse(
        counts={"ObjectType": 1}, total=1,
    )
    r = await client.get("/ontology/v1/drafts/summary")
    assert r.status_code == 200


# ── Snapshots ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_snapshots(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_snapshots.return_value = ([_snapshot()], 1)
    r = await client.post("/ontology/v1/snapshots/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_snapshot(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_snapshot.return_value = _snapshot()
    r = await client.get("/ontology/v1/snapshots/ri.snap.1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_snapshot_diff(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_snapshot_diff.return_value = SnapshotDiffResponse(
        snapshot_changes={}, current_changes={},
    )
    r = await client.get("/ontology/v1/snapshots/ri.snap.1/diff")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_rollback_snapshot(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.rollback_to_snapshot.return_value = _snapshot()
    r = await client.post("/ontology/v1/snapshots/ri.snap.1/rollback")
    assert r.status_code == 200


# ── Topology & Search ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_topology(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_topology.return_value = TopologyResponse(nodes=[], edges=[])
    r = await client.get("/ontology/v1/topology")
    assert r.status_code == 200
    assert r.json()["data"]["nodes"] == []


@pytest.mark.asyncio
async def test_search_entities(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.search.return_value = [
        SearchResultResponse(
            rid="ri.obj.1", api_name="person", display_name="Person",
            entity_type="ObjectType",
        )
    ]
    r = await client.get("/ontology/v1/search?q=person")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


@pytest.mark.asyncio
async def test_search_with_types_filter(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.search.return_value = []
    r = await client.get("/ontology/v1/search?q=test&types=ObjectType,LinkType&limit=10")
    assert r.status_code == 200
    mock_svc.search.assert_awaited_once_with(
        "test", types=["ObjectType", "LinkType"], limit=10,
    )
