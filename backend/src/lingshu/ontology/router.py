"""Ontology module API routes: entity CRUD, versioning, topology, search."""

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.infra.database import get_session
from lingshu.infra.models import ApiResponse, Metadata, PagedResponse, PaginationResponse
from lingshu.ontology.schemas.requests import (
    CommitStagingRequest,
    CreateActionTypeRequest,
    CreateInterfaceTypeRequest,
    CreateLinkTypeRequest,
    CreateObjectTypeRequest,
    CreatePropertyTypeRequest,
    CreateSharedPropertyTypeRequest,
    QueryEntitiesRequest,
    UpdateActionTypeRequest,
    UpdateInterfaceTypeRequest,
    UpdateLinkTypeRequest,
    UpdateObjectTypeRequest,
    UpdateSharedPropertyTypeRequest,
)
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
from lingshu.ontology.service import OntologyServiceImpl

router = APIRouter(prefix="/ontology/v1", tags=["ontology"])

_service: OntologyServiceImpl | None = None


def set_ontology_service(service: OntologyServiceImpl) -> None:
    global _service
    _service = service


def get_ontology_service() -> OntologyServiceImpl:
    if _service is None:
        raise RuntimeError("OntologyService not initialized")
    return _service


async def get_db() -> AsyncGenerator[AsyncSession]:
    async for session in get_session():
        yield session


# ── Helper to build entity routes ────────────────────────────────

def _make_entity_routes(
    entity_key: str,
    label: str,
    create_req_cls: type,
    update_req_cls: type,
) -> None:
    """Register CRUD + lock + versioning routes for an entity type."""
    path = f"/{entity_key}s"

    @router.post(f"{path}/query", name=f"query_{entity_key}s", response_model=None)
    async def query_entities(
        req: QueryEntitiesRequest,
        _label: str = label,
    ) -> PagedResponse[EntityResponse]:
        svc = get_ontology_service()
        offset = (req.pagination.page - 1) * req.pagination.page_size
        entities, total = await svc._query_entities(
            _label, search=req.search,
            lifecycle_status=req.lifecycle_status,
            offset=offset, limit=req.pagination.page_size,
        )
        return PagedResponse(
            data=entities,
            pagination=PaginationResponse(
                total=total, page=req.pagination.page,
                page_size=req.pagination.page_size,
                has_next=(offset + req.pagination.page_size) < total,
            ),
            metadata=Metadata(),
        )

    @router.get(f"{path}/{{rid}}", name=f"get_{entity_key}", response_model=None)
    async def get_entity(
        rid: str,
        _label: str = label,
    ) -> ApiResponse[EntityResponse]:
        svc = get_ontology_service()
        entity = await svc._get_entity(_label, rid)
        return ApiResponse(data=entity)

    @router.get(f"{path}/{{rid}}/draft", name=f"get_{entity_key}_draft", response_model=None)
    async def get_entity_draft(
        rid: str,
        _label: str = label,
    ) -> ApiResponse[EntityResponse]:
        svc = get_ontology_service()
        entity = await svc._get_entity_draft(_label, rid)
        return ApiResponse(data=entity)

    @router.post(f"{path}/{{rid}}/lock", name=f"lock_{entity_key}")
    async def lock_entity(rid: str) -> ApiResponse[LockStatusResponse]:
        svc = get_ontology_service()
        status = await svc.acquire_lock(rid)
        return ApiResponse(data=status)

    @router.put(f"{path}/{{rid}}/lock", name=f"heartbeat_{entity_key}_lock")
    async def heartbeat_lock(rid: str) -> ApiResponse[LockStatusResponse]:
        svc = get_ontology_service()
        status = await svc.refresh_lock(rid)
        return ApiResponse(data=status)

    @router.delete(f"{path}/{{rid}}/lock", name=f"unlock_{entity_key}")
    async def unlock_entity(rid: str) -> ApiResponse[LockStatusResponse]:
        svc = get_ontology_service()
        status = await svc.release_lock(rid)
        return ApiResponse(data=status)

    @router.post(
        f"{path}/{{rid}}/submit-to-staging",
        name=f"submit_{entity_key}_to_staging",
        response_model=None,
    )
    async def submit_to_staging(
        rid: str,
        _label: str = label,
    ) -> ApiResponse[EntityResponse]:
        svc = get_ontology_service()
        entity = await svc.submit_to_staging(_label, rid)
        return ApiResponse(data=entity)

    @router.delete(f"{path}/{{rid}}/draft", name=f"discard_{entity_key}_draft")
    async def discard_draft(
        rid: str,
        _label: str = label,
    ) -> ApiResponse[dict[str, Any]]:
        svc = get_ontology_service()
        await svc.discard_draft(_label, rid)
        return ApiResponse(data={"message": "Draft discarded"})

    @router.delete(
        f"{path}/{{rid}}/staging",
        name=f"discard_{entity_key}_staging",
    )
    async def discard_staging(
        rid: str,
        _label: str = label,
    ) -> ApiResponse[dict[str, Any]]:
        svc = get_ontology_service()
        await svc.discard_staging(_label, rid)
        return ApiResponse(data={"message": "Staging discarded"})

    @router.get(f"{path}/{{rid}}/related", name=f"get_{entity_key}_related")
    async def get_related(
        rid: str,
        _label: str = label,
    ) -> ApiResponse[list[dict[str, Any]]]:
        svc = get_ontology_service()
        related = await svc.get_related(_label, rid)
        return ApiResponse(data=related)


# ── ObjectType routes ─────────────────────────────────────────────

@router.post("/object-types", status_code=201, response_model=None)
async def create_object_type(
    req: CreateObjectTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.create_object_type(req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.put("/object-types/{rid}", response_model=None)
async def update_object_type(
    rid: str, req: UpdateObjectTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.update_object_type(rid, req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.delete("/object-types/{rid}")
async def delete_object_type(rid: str) -> ApiResponse[dict[str, Any]]:
    svc = get_ontology_service()
    await svc.delete_object_type(rid)
    return ApiResponse(data={"message": "Marked for deletion"})


# ── LinkType routes ───────────────────────────────────────────────

@router.post("/link-types", status_code=201, response_model=None)
async def create_link_type(
    req: CreateLinkTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.create_link_type(req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.put("/link-types/{rid}", response_model=None)
async def update_link_type(
    rid: str, req: UpdateLinkTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.update_link_type(rid, req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.delete("/link-types/{rid}")
async def delete_link_type(rid: str) -> ApiResponse[dict[str, Any]]:
    svc = get_ontology_service()
    await svc.delete_link_type(rid)
    return ApiResponse(data={"message": "Marked for deletion"})


# ── InterfaceType routes ──────────────────────────────────────────

@router.post("/interface-types", status_code=201, response_model=None)
async def create_interface_type(
    req: CreateInterfaceTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.create_interface_type(req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.put("/interface-types/{rid}", response_model=None)
async def update_interface_type(
    rid: str, req: UpdateInterfaceTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.update_interface_type(rid, req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.delete("/interface-types/{rid}")
async def delete_interface_type(rid: str) -> ApiResponse[dict[str, Any]]:
    svc = get_ontology_service()
    await svc.delete_interface_type(rid)
    return ApiResponse(data={"message": "Marked for deletion"})


# ── SharedPropertyType routes ─────────────────────────────────────

@router.post("/shared-property-types", status_code=201, response_model=None)
async def create_shared_property_type(
    req: CreateSharedPropertyTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.create_shared_property_type(req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.put("/shared-property-types/{rid}", response_model=None)
async def update_shared_property_type(
    rid: str, req: UpdateSharedPropertyTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.update_shared_property_type(
        rid, req.model_dump(exclude_none=True)
    )
    return ApiResponse(data=entity)


@router.delete("/shared-property-types/{rid}")
async def delete_shared_property_type(rid: str) -> ApiResponse[dict[str, Any]]:
    svc = get_ontology_service()
    await svc.delete_shared_property_type(rid)
    return ApiResponse(data={"message": "Marked for deletion"})


# ── ActionType routes ─────────────────────────────────────────────

@router.post("/action-types", status_code=201, response_model=None)
async def create_action_type(
    req: CreateActionTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.create_action_type(req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.put("/action-types/{rid}", response_model=None)
async def update_action_type(
    rid: str, req: UpdateActionTypeRequest,
) -> ApiResponse[EntityResponse]:
    svc = get_ontology_service()
    entity = await svc.update_action_type(rid, req.model_dump(exclude_none=True))
    return ApiResponse(data=entity)


@router.delete("/action-types/{rid}")
async def delete_action_type(rid: str) -> ApiResponse[dict[str, Any]]:
    svc = get_ontology_service()
    await svc.delete_action_type(rid)
    return ApiResponse(data={"message": "Marked for deletion"})


# ── Register query/get/draft/lock/staging routes for each type ────

_ENTITY_CONFIGS = [
    ("object-type", "ObjectType", CreateObjectTypeRequest, UpdateObjectTypeRequest),
    ("link-type", "LinkType", CreateLinkTypeRequest, UpdateLinkTypeRequest),
    ("interface-type", "InterfaceType", CreateInterfaceTypeRequest, UpdateInterfaceTypeRequest),
    ("shared-property-type", "SharedPropertyType", CreateSharedPropertyTypeRequest, UpdateSharedPropertyTypeRequest),
    ("action-type", "ActionType", CreateActionTypeRequest, UpdateActionTypeRequest),
]

for _key, _label, _create_cls, _update_cls in _ENTITY_CONFIGS:
    _make_entity_routes(_key, _label, _create_cls, _update_cls)


# ── PropertyType independent query ─────────────────────────────────

@router.post("/property-types/query", response_model=None)
async def query_all_property_types(
    req: QueryEntitiesRequest,
) -> PagedResponse[PropertyTypeResponse]:
    svc = get_ontology_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    props, total = await svc.query_all_property_types(
        search=req.search, offset=offset, limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=props,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


# ── AssetMapping query endpoints ──────────────────────────────────

@router.post("/asset-mappings/query", response_model=None)
async def query_all_asset_mappings(
    req: QueryEntitiesRequest,
) -> PagedResponse[dict[str, Any]]:
    svc = get_ontology_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    mappings, total = await svc.query_all_asset_mappings(
        search=req.search, offset=offset, limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=mappings,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/asset-mappings/references", response_model=None)
async def query_asset_mapping_references(
    entity_rid: str = Query(..., description="RID of the entity to get references for"),
) -> ApiResponse[list[dict[str, Any]]]:
    svc = get_ontology_service()
    refs = await svc.query_asset_mapping_references(entity_rid)
    return ApiResponse(data=refs)


# ── PropertyType routes ───────────────────────────────────────────

@router.post("/object-types/{parent_rid}/property-types", status_code=201)
async def create_object_property_type(
    parent_rid: str,
    req: CreatePropertyTypeRequest,
) -> ApiResponse[PropertyTypeResponse]:
    svc = get_ontology_service()
    prop = await svc.create_property_type(
        parent_rid, "ObjectType", req.model_dump(exclude_none=True)
    )
    return ApiResponse(data=prop)


@router.post("/link-types/{parent_rid}/property-types", status_code=201)
async def create_link_property_type(
    parent_rid: str,
    req: CreatePropertyTypeRequest,
) -> ApiResponse[PropertyTypeResponse]:
    svc = get_ontology_service()
    prop = await svc.create_property_type(
        parent_rid, "LinkType", req.model_dump(exclude_none=True)
    )
    return ApiResponse(data=prop)


# ── Version Management ────────────────────────────────────────────

@router.get("/staging/summary")
async def staging_summary() -> ApiResponse[StagingSummaryResponse]:
    svc = get_ontology_service()
    summary = await svc.get_staging_summary()
    return ApiResponse(data=summary)


@router.post("/staging/commit")
async def commit_staging(
    req: CommitStagingRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SnapshotResponse]:
    svc = get_ontology_service()
    snapshot = await svc.commit_staging(req.commit_message, session)
    return ApiResponse(data=snapshot)


@router.post("/staging/discard")
async def discard_all_staging() -> ApiResponse[dict[str, Any]]:
    svc = get_ontology_service()
    count = await svc.discard_all_staging()
    return ApiResponse(data={"discarded": count})


@router.get("/drafts/summary")
async def drafts_summary() -> ApiResponse[DraftsSummaryResponse]:
    svc = get_ontology_service()
    summary = await svc.get_drafts_summary()
    return ApiResponse(data=summary)


# ── Snapshots ─────────────────────────────────────────────────────

@router.post("/snapshots/query")
async def query_snapshots(
    req: QueryEntitiesRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[SnapshotResponse]:
    svc = get_ontology_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    snapshots, total = await svc.query_snapshots(
        session, offset=offset, limit=req.pagination.page_size
    )
    return PagedResponse(
        data=snapshots,
        pagination=PaginationResponse(
            total=total, page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(
    snapshot_id: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SnapshotResponse]:
    svc = get_ontology_service()
    snapshot = await svc.get_snapshot(snapshot_id, session)
    return ApiResponse(data=snapshot)


@router.get("/snapshots/{snapshot_id}/diff")
async def get_snapshot_diff(
    snapshot_id: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SnapshotDiffResponse]:
    svc = get_ontology_service()
    diff = await svc.get_snapshot_diff(snapshot_id, session)
    return ApiResponse(data=diff)


@router.post("/snapshots/{snapshot_id}/rollback")
async def rollback_snapshot(
    snapshot_id: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SnapshotResponse]:
    svc = get_ontology_service()
    snapshot = await svc.rollback_to_snapshot(snapshot_id, session)
    return ApiResponse(data=snapshot)


# ── Topology & Search ─────────────────────────────────────────────

@router.get("/topology")
async def get_topology() -> ApiResponse[TopologyResponse]:
    svc = get_ontology_service()
    topo = await svc.get_topology()
    return ApiResponse(data=topo)


@router.get("/search")
async def search_entities(
    q: str = Query(..., min_length=1),
    types: str = Query("", description="Comma-separated entity types"),
    limit: int = Query(20, ge=1, le=100),
) -> ApiResponse[list[SearchResultResponse]]:
    svc = get_ontology_service()
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    results = await svc.search(q, types=type_list, limit=limit)
    return ApiResponse(data=results)
