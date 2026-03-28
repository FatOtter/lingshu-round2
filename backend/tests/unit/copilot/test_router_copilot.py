"""Router integration tests for Copilot module endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lingshu.copilot.router import get_db, router, set_copilot_service
from lingshu.copilot.schemas.responses import (
    CopilotOverviewResponse,
    SessionResponse,
)
from lingshu.infra.errors import register_exception_handlers
from lingshu.setting.auth.middleware import AuthMiddleware


AUTH_HEADERS = {"X-User-ID": "ri.user.test", "X-Tenant-ID": "ri.tenant.test"}


@pytest.fixture
def mock_svc():
    svc = MagicMock()
    for attr in [
        "create_session", "query_sessions", "get_session",
        "query_models", "register_model", "get_model",
        "query_skills", "register_skill", "get_skill",
        "query_mcp", "connect_mcp", "get_mcp",
        "query_sub_agents", "get_overview",
    ]:
        setattr(svc, attr, AsyncMock())
    set_copilot_service(svc)
    yield svc
    set_copilot_service(None)


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


class TestSessionEndpoints:
    def test_create_session(self, client, mock_svc):
        mock_svc.create_session.return_value = SessionResponse(
            session_id="ri.session.1", mode="agent", status="active",
        )

        resp = client.post(
            "/copilot/v1/sessions",
            json={"mode": "agent", "context": {}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201

    def test_query_sessions(self, client, mock_svc):
        mock_svc.query_sessions.return_value = ([], 0)

        resp = client.post(
            "/copilot/v1/sessions/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0


class TestModelEndpoints:
    def test_query_models(self, client, mock_svc):
        mock_svc.query_models.return_value = ([], 0)

        resp = client.post(
            "/copilot/v1/models/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0


class TestSkillEndpoints:
    def test_query_skills(self, client, mock_svc):
        mock_svc.query_skills.return_value = ([], 0)

        resp = client.post(
            "/copilot/v1/skills/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0


class TestMcpEndpoints:
    def test_query_mcp(self, client, mock_svc):
        mock_svc.query_mcp.return_value = ([], 0)

        resp = client.post(
            "/copilot/v1/mcp/query",
            json={"pagination": {"page": 1, "page_size": 20}},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 0


class TestOverview:
    def test_copilot_overview(self, client, mock_svc):
        mock_svc.get_overview.return_value = CopilotOverviewResponse(
            sessions={"total": 10, "active": 3},
            models={"total": 3},
        )

        resp = client.get("/copilot/v1/overview", headers=AUTH_HEADERS)
        assert resp.status_code == 200
