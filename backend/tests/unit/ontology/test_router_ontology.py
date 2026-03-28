"""Router integration tests for Ontology module endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lingshu.infra.errors import AppError, ErrorCode, register_exception_handlers
from lingshu.ontology.router import get_db, router, set_ontology_service
from lingshu.ontology.schemas.responses import LockStatusResponse, StagingSummaryResponse
from lingshu.setting.auth.middleware import AuthMiddleware


AUTH_HEADERS = {"X-User-ID": "ri.user.test", "X-Tenant-ID": "ri.tenant.test"}


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    for attr in [
        "_query_entities", "_get_entity", "_get_entity_draft",
        "acquire_lock", "get_topology", "search",
        "get_staging_summary", "query_all_property_types",
        "create_object_type", "delete_object_type",
        "get_related", "submit_to_staging", "discard_draft",
    ]:
        setattr(svc, attr, AsyncMock())
    set_ontology_service(svc)
    yield svc
    set_ontology_service(None)


@pytest.fixture
def client(mock_svc):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.add_middleware(AuthMiddleware, dev_mode=True)
    app.state.auth_provider = MagicMock()

    mock_session = AsyncMock()

    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestObjectTypeEndpoints:
    def test_query_object_types(self, client, mock_svc):
        mock_svc._query_entities.return_value = ([], 0)

        resp = client.post(
            "/ontology/v1/object-types/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "pagination" in body
        assert body["pagination"]["total"] == 0

    def test_get_object_type(self, client, mock_svc):
        entity = MagicMock()
        entity.model_dump.return_value = {
            "rid": "ri.obj.1", "api_name": "person",
            "display_name": "Person", "lifecycle_status": "active",
        }
        mock_svc._get_entity.return_value = entity

        resp = client.get("/ontology/v1/object-types/ri.obj.1", headers=AUTH_HEADERS)
        assert resp.status_code == 200

    def test_get_object_type_not_found(self, client, mock_svc):
        mock_svc._get_entity.side_effect = AppError(
            code=ErrorCode.ONTOLOGY_NOT_FOUND,
            message="Entity not found",
        )
        resp = client.get("/ontology/v1/object-types/ri.obj.999", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    def test_get_object_type_draft(self, client, mock_svc):
        draft = MagicMock()
        draft.model_dump.return_value = {
            "rid": "ri.obj.1", "api_name": "person",
            "lifecycle_status": "draft",
        }
        mock_svc._get_entity_draft.return_value = draft

        resp = client.get(
            "/ontology/v1/object-types/ri.obj.1/draft", headers=AUTH_HEADERS
        )
        assert resp.status_code == 200

    def test_lock_object_type(self, client, mock_svc):
        lock_status = LockStatusResponse(
            rid="ri.obj.1", locked=True, locked_by="ri.user.test",
        )
        mock_svc.acquire_lock.return_value = lock_status

        resp = client.post(
            "/ontology/v1/object-types/ri.obj.1/lock", headers=AUTH_HEADERS
        )
        assert resp.status_code == 200


class TestTopologyAndSearch:
    def test_get_topology(self, client, mock_svc):
        topo = MagicMock()
        topo.model_dump.return_value = {"nodes": [], "edges": []}
        mock_svc.get_topology.return_value = topo

        resp = client.get("/ontology/v1/topology", headers=AUTH_HEADERS)
        assert resp.status_code == 200

    def test_search_entities(self, client, mock_svc):
        mock_svc.search.return_value = []

        resp = client.get("/ontology/v1/search?q=test", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_search_missing_query(self, client, mock_svc):
        resp = client.get("/ontology/v1/search", headers=AUTH_HEADERS)
        assert resp.status_code == 422


class TestVersionManagement:
    def test_staging_summary(self, client, mock_svc):
        summary = StagingSummaryResponse(counts={}, total=0)
        mock_svc.get_staging_summary.return_value = summary

        resp = client.get("/ontology/v1/staging/summary", headers=AUTH_HEADERS)
        assert resp.status_code == 200


class TestPropertyTypes:
    def test_query_property_types(self, client, mock_svc):
        mock_svc.query_all_property_types.return_value = ([], 0)

        resp = client.post(
            "/ontology/v1/property-types/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0
