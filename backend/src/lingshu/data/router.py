"""Data module API routes: connections, instance queries, overview."""

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.data.schemas.requests import (
    CreateBranchRequest,
    CreateConnectionRequest,
    GetInstanceRequest,
    MergeBranchRequest,
    QueryConnectionsRequest,
    QueryInstancesRequest,
    UpdateConnectionRequest,
)
from lingshu.data.schemas.responses import (
    BranchResponse,
    ConnectionResponse,
    ConnectionTestResponse,
    DataOverviewResponse,
    InstanceQueryResponse,
)
from lingshu.data.service import DataServiceImpl
from lingshu.infra.context import get_tenant_id
from lingshu.infra.database import get_session
from lingshu.infra.models import ApiResponse, Metadata, PagedResponse, PaginationResponse

router = APIRouter(prefix="/data/v1", tags=["data"])

_service: DataServiceImpl | None = None


def set_data_service(service: DataServiceImpl) -> None:
    global _service
    _service = service


def get_data_service() -> DataServiceImpl:
    if _service is None:
        raise RuntimeError("DataService not initialized")
    return _service


async def get_db() -> AsyncGenerator[AsyncSession]:
    async for session in get_session():
        yield session


# ── Connection API ────────────────────────────────────────────────

@router.post("/connections", status_code=201)
async def create_connection(
    req: CreateConnectionRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ConnectionResponse]:
    svc = get_data_service()
    conn = await svc.create_connection(
        req.display_name, req.type, req.config, req.credentials, session
    )
    return ApiResponse(data=conn)


@router.post("/connections/query")
async def query_connections(
    req: QueryConnectionsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[ConnectionResponse]:
    svc = get_data_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    conns, total = await svc.query_connections(
        session, conn_type=req.type, offset=offset, limit=req.pagination.page_size
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


@router.get("/connections/{rid}")
async def get_connection(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ConnectionResponse]:
    svc = get_data_service()
    conn = await svc.get_connection(rid, session)
    return ApiResponse(data=conn)


@router.put("/connections/{rid}")
async def update_connection(
    rid: str,
    req: UpdateConnectionRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ConnectionResponse]:
    svc = get_data_service()
    conn = await svc.update_connection(
        rid, req.model_dump(exclude_none=True), session
    )
    return ApiResponse(data=conn)


@router.delete("/connections/{rid}")
async def delete_connection(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_data_service()
    await svc.delete_connection(rid, session)
    return ApiResponse(data={"message": "Connection deleted"})


@router.post("/connections/{rid}/test")
async def test_connection(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[ConnectionTestResponse]:
    svc = get_data_service()
    result = await svc.test_connection(rid, session)
    return ApiResponse(data=result)


# ── Instance Query API ────────────────────────────────────────────

@router.post("/objects/{type_rid}/instances/query")
async def query_object_instances(
    type_rid: str,
    req: QueryInstancesRequest,
) -> ApiResponse[InstanceQueryResponse]:
    svc = get_data_service()
    tenant_id = get_tenant_id()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    result = await svc.query_instances(
        type_rid, tenant_id, req.filters, req.sort,
        offset=offset, limit=req.pagination.page_size,
    )
    return ApiResponse(data=InstanceQueryResponse(**result))


@router.post("/objects/{type_rid}/instances/get")
async def get_object_instance(
    type_rid: str,
    req: GetInstanceRequest,
) -> ApiResponse[dict[str, Any]]:
    svc = get_data_service()
    tenant_id = get_tenant_id()
    instance = await svc.get_instance(type_rid, tenant_id, req.primary_key)
    return ApiResponse(data=instance or {})


@router.post("/links/{type_rid}/instances/query")
async def query_link_instances(
    type_rid: str,
    req: QueryInstancesRequest,
) -> ApiResponse[InstanceQueryResponse]:
    svc = get_data_service()
    tenant_id = get_tenant_id()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    result = await svc.query_instances(
        type_rid, tenant_id, req.filters, req.sort,
        offset=offset, limit=req.pagination.page_size,
    )
    return ApiResponse(data=InstanceQueryResponse(**result))


@router.post("/links/{type_rid}/instances/get")
async def get_link_instance(
    type_rid: str,
    req: GetInstanceRequest,
) -> ApiResponse[dict[str, Any]]:
    svc = get_data_service()
    tenant_id = get_tenant_id()
    instance = await svc.get_instance(type_rid, tenant_id, req.primary_key)
    return ApiResponse(data=instance or {})


# ── Overview API ──────────────────────────────────────────────────

@router.get("/overview")
async def data_overview(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[DataOverviewResponse]:
    svc = get_data_service()
    data = await svc.get_overview(session)
    return ApiResponse(data=DataOverviewResponse(**data))


# ── Branch Management API ────────────────────────────────────────

@router.get("/branches")
async def list_branches() -> ApiResponse[list[BranchResponse]]:
    svc = get_data_service()
    branches = await svc.list_branches()
    return ApiResponse(data=[BranchResponse(**b) for b in branches])


@router.get("/branches/{name}")
async def get_branch(name: str) -> ApiResponse[BranchResponse]:
    svc = get_data_service()
    branch = await svc.get_branch(name)
    return ApiResponse(data=BranchResponse(**branch))


@router.post("/branches", status_code=201)
async def create_branch(req: CreateBranchRequest) -> ApiResponse[BranchResponse]:
    svc = get_data_service()
    branch = await svc.create_branch(req.name, req.from_ref)
    return ApiResponse(data=BranchResponse(**branch))


@router.delete("/branches/{name}")
async def delete_branch(name: str) -> ApiResponse[dict[str, Any]]:
    svc = get_data_service()
    await svc.delete_branch(name)
    return ApiResponse(data={"message": f"Branch '{name}' deleted"})


@router.post("/branches/{name}/merge")
async def merge_branch(
    name: str, req: MergeBranchRequest,
) -> ApiResponse[dict[str, Any]]:
    svc = get_data_service()
    result = await svc.merge_branch(name, req.target)
    return ApiResponse(data=result)


@router.get("/branches/{from_ref}/diff/{to_ref}")
async def diff_branches(
    from_ref: str, to_ref: str,
) -> ApiResponse[list[dict[str, Any]]]:
    svc = get_data_service()
    diffs = await svc.diff_branches(from_ref, to_ref)
    return ApiResponse(data=diffs)
