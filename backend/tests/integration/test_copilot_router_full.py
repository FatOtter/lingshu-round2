"""Comprehensive integration tests for Copilot module router endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lingshu.copilot.router import router, set_copilot_service
from lingshu.copilot.schemas.responses import (
    CopilotOverviewResponse,
    McpConnectionResponse,
    ModelResponse,
    SessionResponse,
    SkillResponse,
    SubAgentResponse,
)
from lingshu.infra.errors import register_exception_handlers


# ── Helpers ────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(UTC)


def _session(**overrides: Any) -> SessionResponse:
    defaults = dict(
        session_id="ri.session.1", mode="agent", title="Test",
        context={}, status="active", created_at=_now(), last_active_at=_now(),
    )
    return SessionResponse(**(defaults | overrides))


def _model(**overrides: Any) -> ModelResponse:
    defaults = dict(
        rid="ri.model.1", api_name="gpt4", display_name="GPT-4",
        provider="openai", connection={"api_key": "***"},
        parameters={"temperature": 0.7}, is_default=True,
        created_at=_now(), updated_at=_now(),
    )
    return ModelResponse(**(defaults | overrides))


def _skill(**overrides: Any) -> SkillResponse:
    defaults = dict(
        rid="ri.skill.1", api_name="code_review", display_name="Code Review",
        description="Reviews code", system_prompt="You are a code reviewer",
        tool_bindings=[], enabled=True, created_at=_now(), updated_at=_now(),
    )
    return SkillResponse(**(defaults | overrides))


def _mcp(**overrides: Any) -> McpConnectionResponse:
    defaults = dict(
        rid="ri.mcp.1", api_name="github", display_name="GitHub MCP",
        description="GitHub tools", transport={"type": "sse", "url": "http://localhost:3000"},
        discovered_tools=[], status="connected", enabled=True,
        created_at=_now(), updated_at=_now(),
    )
    return McpConnectionResponse(**(defaults | overrides))


def _subagent(**overrides: Any) -> SubAgentResponse:
    defaults = dict(
        rid="ri.subagent.1", api_name="researcher", display_name="Researcher",
        description="Research agent", model_rid="ri.model.1",
        system_prompt="You are a researcher", tool_bindings=[],
        safety_policy={}, enabled=True, created_at=_now(), updated_at=_now(),
    )
    return SubAgentResponse(**(defaults | overrides))


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def mock_svc() -> MagicMock:
    svc = MagicMock()
    # Sessions
    svc.create_session = AsyncMock()
    svc.get_session = AsyncMock()
    svc.query_sessions = AsyncMock()
    svc.update_context = AsyncMock()
    svc.delete_session = AsyncMock()
    # Messages (SSE)
    svc.send_message = AsyncMock()
    svc.resume_execution = AsyncMock()
    # Models
    svc.register_model = AsyncMock()
    svc.query_models = AsyncMock()
    svc.get_model = AsyncMock()
    svc.update_model = AsyncMock()
    svc.delete_model = AsyncMock()
    # Skills
    svc.register_skill = AsyncMock()
    svc.query_skills = AsyncMock()
    svc.get_skill = AsyncMock()
    svc.update_skill = AsyncMock()
    svc.delete_skill = AsyncMock()
    # MCP
    svc.connect_mcp = AsyncMock()
    svc.query_mcp = AsyncMock()
    svc.get_mcp = AsyncMock()
    svc.update_mcp = AsyncMock()
    svc.delete_mcp = AsyncMock()
    svc.discover_mcp_tools = AsyncMock()
    svc.test_mcp_connection = AsyncMock()
    # Sub-Agents
    svc.create_sub_agent = AsyncMock()
    svc.query_sub_agents = AsyncMock()
    svc.get_sub_agent = AsyncMock()
    svc.update_sub_agent = AsyncMock()
    svc.delete_sub_agent = AsyncMock()
    # Overview
    svc.get_overview = AsyncMock()
    return svc


@pytest.fixture
def app(mock_svc: MagicMock) -> FastAPI:
    _app = FastAPI()
    register_exception_handlers(_app)
    _app.include_router(router)
    set_copilot_service(mock_svc)  # type: ignore[arg-type]
    return _app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _override_db(app: FastAPI) -> None:
    from lingshu.copilot.router import get_db

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _fake_db


# ── Session Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_session.return_value = _session()
    r = await client.post("/copilot/v1/sessions", json={
        "mode": "agent", "context": {"page": "ontology"},
    })
    assert r.status_code == 201
    assert r.json()["data"]["session_id"] == "ri.session.1"


@pytest.mark.asyncio
async def test_get_session(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_session.return_value = _session()
    r = await client.get("/copilot/v1/sessions/ri.session.1")
    assert r.status_code == 200
    assert r.json()["data"]["mode"] == "agent"


@pytest.mark.asyncio
async def test_query_sessions(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_sessions.return_value = ([_session()], 1)
    r = await client.post("/copilot/v1/sessions/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_update_session_context(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_context.return_value = _session(context={"page": "data"})
    r = await client.put("/copilot/v1/sessions/ri.session.1/context", json={
        "context": {"page": "data"},
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_session(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/copilot/v1/sessions/ri.session.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Session deleted"


# ── Message SSE Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_message_returns_sse(client: AsyncClient, mock_svc: MagicMock) -> None:
    event = MagicMock()
    event.to_sse.return_value = "data: {\"type\": \"text\", \"content\": \"hello\"}\n\n"

    async def _gen(sid, content, session):
        yield event

    mock_svc.send_message = _gen
    r = await client.post("/copilot/v1/sessions/ri.session.1/messages", json={
        "content": "Hello, what can you do?",
    })
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")


@pytest.mark.asyncio
async def test_resume_execution_returns_sse(client: AsyncClient, mock_svc: MagicMock) -> None:
    event = MagicMock()
    event.to_sse.return_value = "data: {\"type\": \"done\"}\n\n"

    async def _gen(sid, approved, session):
        yield event

    mock_svc.resume_execution = _gen
    r = await client.post("/copilot/v1/sessions/ri.session.1/resume", json={
        "approved": True,
    })
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")


# ── Model Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_model(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.register_model.return_value = _model()
    r = await client.post("/copilot/v1/models", json={
        "api_name": "gpt4", "display_name": "GPT-4",
        "provider": "openai", "connection": {},
        "parameters": {"temperature": 0.7}, "is_default": True,
    })
    assert r.status_code == 201
    assert r.json()["data"]["rid"] == "ri.model.1"


@pytest.mark.asyncio
async def test_query_models(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_models.return_value = ([_model()], 1)
    r = await client.post("/copilot/v1/models/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_model(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_model.return_value = _model()
    r = await client.get("/copilot/v1/models/ri.model.1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_model(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_model.return_value = _model(display_name="GPT-4 Turbo")
    r = await client.put("/copilot/v1/models/ri.model.1", json={
        "display_name": "GPT-4 Turbo",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_model(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/copilot/v1/models/ri.model.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Model deleted"


# ── Skill Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_skill(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.register_skill.return_value = _skill()
    r = await client.post("/copilot/v1/skills", json={
        "api_name": "code_review", "display_name": "Code Review",
        "system_prompt": "You are a code reviewer",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_query_skills(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_skills.return_value = ([_skill()], 1)
    r = await client.post("/copilot/v1/skills/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_skill(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_skill.return_value = _skill()
    r = await client.get("/copilot/v1/skills/ri.skill.1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_skill(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_skill.return_value = _skill(display_name="Updated")
    r = await client.put("/copilot/v1/skills/ri.skill.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_skill(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/copilot/v1/skills/ri.skill.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Skill deleted"


# ── MCP Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_mcp(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.connect_mcp.return_value = _mcp()
    r = await client.post("/copilot/v1/mcp", json={
        "api_name": "github", "display_name": "GitHub MCP",
        "transport": {"type": "sse", "url": "http://localhost:3000"},
    })
    assert r.status_code == 201
    assert r.json()["data"]["rid"] == "ri.mcp.1"


@pytest.mark.asyncio
async def test_query_mcp(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_mcp.return_value = ([_mcp()], 1)
    r = await client.post("/copilot/v1/mcp/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_mcp(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_mcp.return_value = _mcp()
    r = await client.get("/copilot/v1/mcp/ri.mcp.1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_mcp(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_mcp.return_value = _mcp(display_name="Updated")
    r = await client.put("/copilot/v1/mcp/ri.mcp.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_mcp(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/copilot/v1/mcp/ri.mcp.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "MCP connection deleted"


@pytest.mark.asyncio
async def test_discover_tools(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.discover_mcp_tools.return_value = [
        {"name": "search", "description": "Search GitHub"},
    ]
    r = await client.post("/copilot/v1/mcp/ri.mcp.1/discover-tools")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1


@pytest.mark.asyncio
async def test_test_mcp_connection(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.test_mcp_connection.return_value = {"status": "ok", "latency_ms": 50}
    r = await client.post("/copilot/v1/mcp/ri.mcp.1/test")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


# ── Sub-Agent Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_sub_agent(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.create_sub_agent.return_value = _subagent()
    r = await client.post("/copilot/v1/sub-agents", json={
        "api_name": "researcher", "display_name": "Researcher",
        "model_rid": "ri.model.1",
    })
    assert r.status_code == 201
    assert r.json()["data"]["rid"] == "ri.subagent.1"


@pytest.mark.asyncio
async def test_query_sub_agents(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.query_sub_agents.return_value = ([_subagent()], 1)
    r = await client.post("/copilot/v1/sub-agents/query", json={
        "pagination": {"page": 1, "page_size": 20},
    })
    assert r.status_code == 200
    assert r.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_sub_agent(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_sub_agent.return_value = _subagent()
    r = await client.get("/copilot/v1/sub-agents/ri.subagent.1")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_update_sub_agent(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.update_sub_agent.return_value = _subagent(display_name="Updated")
    r = await client.put("/copilot/v1/sub-agents/ri.subagent.1", json={
        "display_name": "Updated",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_sub_agent(client: AsyncClient, mock_svc: MagicMock) -> None:
    r = await client.delete("/copilot/v1/sub-agents/ri.subagent.1")
    assert r.status_code == 200
    assert r.json()["data"]["message"] == "Sub-agent deleted"


# ── Overview ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_copilot_overview(client: AsyncClient, mock_svc: MagicMock) -> None:
    mock_svc.get_overview.return_value = CopilotOverviewResponse(
        sessions={"total": 10, "active": 3},
        models={"total": 2},
    )
    r = await client.get("/copilot/v1/overview")
    assert r.status_code == 200
    assert r.json()["data"]["sessions"]["total"] == 10
