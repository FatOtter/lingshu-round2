"""Function module API routes: actions, global functions, executions, capabilities."""

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.function.schemas.requests import (
    CreateGlobalFunctionRequest,
    CreateWorkflowRequest,
    ExecuteActionBatchRequest,
    ExecuteActionRequest,
    ExecuteGlobalFunctionRequest,
    ExecuteWorkflowRequest,
    QueryCapabilitiesRequest,
    QueryExecutionsRequest,
    QueryWorkflowsRequest,
    UpdateGlobalFunctionRequest,
    UpdateWorkflowRequest,
)
from lingshu.function.schemas.responses import (
    CapabilityDescriptor,
    ExecutionDetailResponse,
    ExecutionResponse,
    FunctionOverviewResponse,
    GlobalFunctionResponse,
    WorkflowExecutionResponse,
    WorkflowResponse,
)
from lingshu.function.service import FunctionServiceImpl
from lingshu.function.workflows.service import WorkflowService
from lingshu.infra.database import get_session
from lingshu.infra.models import ApiResponse, Metadata, PagedResponse, PaginationResponse

router = APIRouter(prefix="/function/v1", tags=["function"])

_service: FunctionServiceImpl | None = None
_workflow_service: WorkflowService | None = None


def set_function_service(service: FunctionServiceImpl) -> None:
    global _service
    _service = service


def get_function_service() -> FunctionServiceImpl:
    if _service is None:
        raise RuntimeError("FunctionService not initialized")
    return _service


def set_workflow_service(service: WorkflowService) -> None:
    global _workflow_service
    _workflow_service = service


def get_workflow_service() -> WorkflowService:
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowService()
    return _workflow_service


async def get_db() -> AsyncGenerator[AsyncSession]:
    async for session in get_session():
        yield session


# ── Action Execution API ─────────────────────────────────────────

@router.post("/actions/{action_type_rid}/execute")
async def execute_action(
    action_type_rid: str,
    req: ExecuteActionRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ExecutionResponse]:
    svc = get_function_service()
    result = await svc.execute_action(
        action_type_rid,
        req.params,
        session,
        branch=req.branch,
        skip_confirmation=req.skip_confirmation,
    )
    return ApiResponse(data=result)


@router.post("/actions/{action_type_rid}/execute/batch")
async def execute_action_batch(
    action_type_rid: str,
    req: ExecuteActionBatchRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    svc = get_function_service()
    result = await svc.execute_action_batch(
        action_type_rid,
        req.batch_params,
        session,
        branch=req.branch,
        skip_confirmation=req.skip_confirmation,
    )
    return ApiResponse(data=result)


@router.post("/actions/{action_type_rid}/execute/async")
async def execute_action_async(
    action_type_rid: str,
    req: ExecuteActionRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ExecutionResponse]:
    svc = get_function_service()
    result = await svc.execute_action_async(
        action_type_rid,
        req.params,
        session,
        branch=req.branch,
        skip_confirmation=req.skip_confirmation,
    )
    return ApiResponse(data=result)


@router.get("/actions/{action_type_rid}")
async def get_action_detail(
    action_type_rid: str,
) -> ApiResponse[dict[str, Any]]:
    svc = get_function_service()
    action_def = await svc._loader.load(action_type_rid)
    return ApiResponse(data={
        "rid": action_def.rid,
        "api_name": action_def.api_name,
        "display_name": action_def.display_name,
        "parameters": action_def.parameters,
        "safety_level": action_def.safety_level,
        "side_effects": action_def.side_effects,
    })


# ── Global Function API ─────────────────────────────────────────

@router.post("/functions", status_code=201)
async def create_function(
    req: CreateGlobalFunctionRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[GlobalFunctionResponse]:
    svc = get_function_service()
    func = await svc.create_function(
        req.api_name, req.display_name, req.description,
        req.parameters, req.implementation, session,
    )
    return ApiResponse(data=func)


@router.post("/functions/query")
async def query_functions(
    req: QueryCapabilitiesRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[GlobalFunctionResponse]:
    svc = get_function_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    funcs, total = await svc.query_functions(
        session, offset=offset, limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=funcs,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/functions/{rid}")
async def get_function(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[GlobalFunctionResponse]:
    svc = get_function_service()
    func = await svc.get_function(rid, session)
    return ApiResponse(data=func)


@router.put("/functions/{rid}")
async def update_function(
    rid: str,
    req: UpdateGlobalFunctionRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[GlobalFunctionResponse]:
    svc = get_function_service()
    func = await svc.update_function(
        rid, req.model_dump(exclude_none=True), session,
    )
    return ApiResponse(data=func)


@router.delete("/functions/{rid}")
async def delete_function(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_function_service()
    await svc.delete_function(rid, session)
    return ApiResponse(data={"message": "Function deleted"})


@router.post("/functions/{rid}/execute")
async def execute_function(
    rid: str,
    req: ExecuteGlobalFunctionRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ExecutionResponse]:
    svc = get_function_service()
    result = await svc.execute_function(
        rid, req.params, session, branch=req.branch,
    )
    return ApiResponse(data=result)


# ── Execution Management API ────────────────────────────────────

@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ExecutionDetailResponse]:
    svc = get_function_service()
    execution = await svc.get_execution(execution_id, session)
    return ApiResponse(data=execution)


@router.post("/executions/query")
async def query_executions(
    req: QueryExecutionsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[ExecutionDetailResponse]:
    svc = get_function_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    executions, total = await svc.query_executions(
        session,
        offset=offset,
        limit=req.pagination.page_size,
        capability_type=req.capability_type,
        status=req.status,
    )
    return PagedResponse(
        data=executions,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.post("/executions/{execution_id}/confirm")
async def confirm_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ExecutionResponse]:
    svc = get_function_service()
    result = await svc.confirm_execution(execution_id, session)
    return ApiResponse(data=result)


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ExecutionResponse]:
    svc = get_function_service()
    result = await svc.cancel_execution(execution_id, session)
    return ApiResponse(data=result)


# ── Capability Catalog API ───────────────────────────────────────

@router.post("/capabilities/query")
async def query_capabilities(
    req: QueryCapabilitiesRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[list[CapabilityDescriptor]]:
    svc = get_function_service()
    capabilities = await svc.list_capabilities(
        session, capability_type=req.capability_type,
    )
    return ApiResponse(data=capabilities)


# ── Overview API ─────────────────────────────────────────────────

@router.get("/overview")
async def function_overview(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[FunctionOverviewResponse]:
    svc = get_function_service()
    overview = await svc.get_overview(session)
    return ApiResponse(data=overview)


# ── Workflow API ─────────────────────────────────────────────────

@router.post("/workflows", status_code=201)
async def create_workflow(
    req: CreateWorkflowRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkflowResponse]:
    svc = get_workflow_service()
    nodes = [n.model_dump() for n in req.nodes]
    edges = [e.model_dump() for e in req.edges]
    wf = await svc.create_workflow(
        req.api_name, req.display_name, req.description,
        nodes, edges, req.status, session,
    )
    return ApiResponse(data=wf)


@router.post("/workflows/query")
async def query_workflows(
    req: QueryWorkflowsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[WorkflowResponse]:
    svc = get_workflow_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    workflows, total = await svc.query_workflows(
        session, offset=offset, limit=req.pagination.page_size,
        status=req.status,
    )
    return PagedResponse(
        data=workflows,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/workflows/{rid}")
async def get_workflow(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkflowResponse]:
    svc = get_workflow_service()
    wf = await svc.get_workflow(rid, session)
    return ApiResponse(data=wf)


@router.put("/workflows/{rid}")
async def update_workflow(
    rid: str,
    req: UpdateWorkflowRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkflowResponse]:
    svc = get_workflow_service()
    updates = req.model_dump(exclude_none=True)
    if "nodes" in updates:
        updates["nodes"] = [n.model_dump() for n in req.nodes] if req.nodes else []
    if "edges" in updates:
        updates["edges"] = [e.model_dump() for e in req.edges] if req.edges else []
    wf = await svc.update_workflow(rid, updates, session)
    return ApiResponse(data=wf)


@router.delete("/workflows/{rid}")
async def delete_workflow(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_workflow_service()
    await svc.delete_workflow(rid, session)
    return ApiResponse(data={"message": "Workflow deleted"})


@router.post("/workflows/{rid}/execute")
async def execute_workflow(
    rid: str,
    req: ExecuteWorkflowRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[WorkflowExecutionResponse]:
    svc = get_workflow_service()
    result = await svc.execute_workflow(rid, req.inputs, session)
    return ApiResponse(data=result)
