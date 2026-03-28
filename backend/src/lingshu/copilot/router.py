"""Copilot module API routes: sessions, messages (SSE), models."""

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.schemas.requests import (
    ConnectMcpRequest,
    CreateSessionRequest,
    CreateSkillRequest,
    CreateSubAgentRequest,
    QueryMcpRequest,
    QuerySessionsRequest,
    QuerySkillsRequest,
    QuerySubAgentsRequest,
    RegisterModelRequest,
    ResumeRequest,
    SendMessageRequest,
    UpdateContextRequest,
    UpdateMcpRequest,
    UpdateModelRequest,
    UpdateSkillRequest,
    UpdateSubAgentRequest,
)
from lingshu.copilot.schemas.responses import (
    CopilotOverviewResponse,
    McpConnectionResponse,
    ModelResponse,
    SessionResponse,
    SkillResponse,
    SubAgentResponse,
)
from lingshu.copilot.service import CopilotServiceImpl
from lingshu.infra.database import get_session
from lingshu.infra.models import ApiResponse, Metadata, PagedResponse, PaginationResponse

router = APIRouter(prefix="/copilot/v1", tags=["copilot"])

_service: CopilotServiceImpl | None = None


def set_copilot_service(service: CopilotServiceImpl) -> None:
    global _service
    _service = service


def get_copilot_service() -> CopilotServiceImpl:
    if _service is None:
        raise RuntimeError("CopilotService not initialized")
    return _service


async def get_db() -> AsyncGenerator[AsyncSession]:
    async for session in get_session():
        yield session


# ── Session API ──────────────────────────────────────────────────

@router.post("/sessions", status_code=201)
async def create_session(
    req: CreateSessionRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SessionResponse]:
    svc = get_copilot_service()
    result = await svc.create_session(req.mode, req.context, session)
    return ApiResponse(data=result)


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SessionResponse]:
    svc = get_copilot_service()
    result = await svc.get_session(session_id, session)
    return ApiResponse(data=result)


@router.post("/sessions/query")
async def query_sessions(
    req: QuerySessionsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[SessionResponse]:
    svc = get_copilot_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    sessions, total = await svc.query_sessions(
        session, offset=offset, limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=sessions,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.put("/sessions/{session_id}/context")
async def update_session_context(
    session_id: str,
    req: UpdateContextRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SessionResponse]:
    svc = get_copilot_service()
    result = await svc.update_context(session_id, req.context, session)
    return ApiResponse(data=result)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_copilot_service()
    await svc.delete_session(session_id, session)
    return ApiResponse(data={"message": "Session deleted"})


# ── Message API (SSE) ────────────────────────────────────────────

@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    req: SendMessageRequest,
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    svc = get_copilot_service()

    async def event_stream() -> AsyncGenerator[str]:
        async for event in svc.send_message(session_id, req.content, session):
            yield event.to_sse()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/resume")
async def resume_execution(
    session_id: str,
    req: ResumeRequest,
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    svc = get_copilot_service()

    async def event_stream() -> AsyncGenerator[str]:
        async for event in svc.resume_execution(
            session_id, req.approved, session,
        ):
            yield event.to_sse()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Model API ────────────────────────────────────────────────────

@router.post("/models", status_code=201)
async def register_model(
    req: RegisterModelRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ModelResponse]:
    svc = get_copilot_service()
    model = await svc.register_model(
        req.api_name, req.display_name, req.provider,
        req.connection, req.parameters, req.is_default, session,
    )
    return ApiResponse(data=model)


@router.post("/models/query")
async def query_models(
    req: QuerySessionsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[ModelResponse]:
    svc = get_copilot_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    models, total = await svc.query_models(
        session, offset=offset, limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=models,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/models/{rid}")
async def get_model(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ModelResponse]:
    svc = get_copilot_service()
    model = await svc.get_model(rid, session)
    return ApiResponse(data=model)


@router.put("/models/{rid}")
async def update_model(
    rid: str,
    req: UpdateModelRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ModelResponse]:
    svc = get_copilot_service()
    model = await svc.update_model(
        rid, req.model_dump(exclude_none=True), session,
    )
    return ApiResponse(data=model)


@router.delete("/models/{rid}")
async def delete_model(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_copilot_service()
    await svc.delete_model(rid, session)
    return ApiResponse(data={"message": "Model deleted"})


# ── Skill API ────────────────────────────────────────────────────

@router.post("/skills", status_code=201)
async def register_skill(
    req: CreateSkillRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SkillResponse]:
    svc = get_copilot_service()
    skill = await svc.register_skill(
        req.api_name, req.display_name, req.description,
        req.system_prompt, req.tool_bindings, session,
    )
    return ApiResponse(data=skill)


@router.post("/skills/query")
async def query_skills(
    req: QuerySkillsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[SkillResponse]:
    svc = get_copilot_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    skills, total = await svc.query_skills(
        session, offset=offset, limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=skills,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/skills/{rid}")
async def get_skill(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SkillResponse]:
    svc = get_copilot_service()
    skill = await svc.get_skill(rid, session)
    return ApiResponse(data=skill)


@router.put("/skills/{rid}")
async def update_skill(
    rid: str,
    req: UpdateSkillRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SkillResponse]:
    svc = get_copilot_service()
    skill = await svc.update_skill(
        rid, req.model_dump(exclude_none=True), session,
    )
    return ApiResponse(data=skill)


@router.delete("/skills/{rid}")
async def delete_skill(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_copilot_service()
    await svc.delete_skill(rid, session)
    return ApiResponse(data={"message": "Skill deleted"})


# ── MCP API ──────────────────────────────────────────────────────

@router.post("/mcp", status_code=201)
async def connect_mcp(
    req: ConnectMcpRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[McpConnectionResponse]:
    svc = get_copilot_service()
    conn = await svc.connect_mcp(
        req.api_name, req.display_name, req.description,
        req.transport, req.auth, session,
    )
    return ApiResponse(data=conn)


@router.post("/mcp/query")
async def query_mcp(
    req: QueryMcpRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[McpConnectionResponse]:
    svc = get_copilot_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    conns, total = await svc.query_mcp(
        session, offset=offset, limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=conns,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/mcp/{rid}")
async def get_mcp(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[McpConnectionResponse]:
    svc = get_copilot_service()
    conn = await svc.get_mcp(rid, session)
    return ApiResponse(data=conn)


@router.put("/mcp/{rid}")
async def update_mcp(
    rid: str,
    req: UpdateMcpRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[McpConnectionResponse]:
    svc = get_copilot_service()
    conn = await svc.update_mcp(
        rid, req.model_dump(exclude_none=True), session,
    )
    return ApiResponse(data=conn)


@router.delete("/mcp/{rid}")
async def delete_mcp(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_copilot_service()
    await svc.delete_mcp(rid, session)
    return ApiResponse(data={"message": "MCP connection deleted"})


@router.post("/mcp/{rid}/discover-tools")
async def discover_tools(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[list[dict[str, Any]]]:
    svc = get_copilot_service()
    tools = await svc.discover_mcp_tools(rid, session)
    return ApiResponse(data=tools)


@router.post("/mcp/{rid}/test")
async def test_connection(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_copilot_service()
    result = await svc.test_mcp_connection(rid, session)
    return ApiResponse(data=result)


# ── Sub-Agent API ────────────────────────────────────────────────

@router.post("/sub-agents", status_code=201)
async def create_sub_agent(
    req: CreateSubAgentRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SubAgentResponse]:
    svc = get_copilot_service()
    agent = await svc.create_sub_agent(
        req.api_name, req.display_name, req.description,
        req.model_rid, req.system_prompt, req.tool_bindings,
        req.safety_policy, req.enabled, session,
    )
    return ApiResponse(data=agent)


@router.post("/sub-agents/query")
async def query_sub_agents(
    req: QuerySubAgentsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[SubAgentResponse]:
    svc = get_copilot_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    agents, total = await svc.query_sub_agents(
        session, offset=offset, limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=agents,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/sub-agents/{rid}")
async def get_sub_agent(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SubAgentResponse]:
    svc = get_copilot_service()
    agent = await svc.get_sub_agent(rid, session)
    return ApiResponse(data=agent)


@router.put("/sub-agents/{rid}")
async def update_sub_agent(
    rid: str,
    req: UpdateSubAgentRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SubAgentResponse]:
    svc = get_copilot_service()
    agent = await svc.update_sub_agent(
        rid, req.model_dump(exclude_none=True), session,
    )
    return ApiResponse(data=agent)


@router.delete("/sub-agents/{rid}")
async def delete_sub_agent(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_copilot_service()
    await svc.delete_sub_agent(rid, session)
    return ApiResponse(data={"message": "Sub-agent deleted"})


# ── Overview API ─────────────────────────────────────────────────

@router.get("/overview")
async def copilot_overview(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[CopilotOverviewResponse]:
    svc = get_copilot_service()
    overview = await svc.get_overview(session)
    return ApiResponse(data=overview)
