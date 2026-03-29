"""Ontology service: CRUD for all entity types + version management + locks."""

import contextlib
import json
import logging
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.infra.context import get_tenant_id, get_user_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.rid import generate_rid
from lingshu.ontology.models import Snapshot
from lingshu.ontology.repository.graph_repo import ENTITY_LABELS, GraphRepository
from lingshu.ontology.repository.snapshot_repo import SnapshotRepository
from lingshu.ontology.retry import retry_neo4j_operation
from lingshu.ontology.schemas.responses import (
    ActionTypeResponse,
    DraftsSummaryResponse,
    EntityResponse,
    InterfaceTypeResponse,
    LinkTypeResponse,
    LockStatusResponse,
    ObjectTypeResponse,
    PropertyTypeResponse,
    SearchResultResponse,
    SharedPropertyTypeResponse,
    SnapshotDiffResponse,
    SnapshotResponse,
    StagingSummaryResponse,
    TopologyResponse,
)
from lingshu.ontology.validators.cascade import cascade_shared_property_update
from lingshu.ontology.validators.contract import check_contract_satisfaction
from lingshu.ontology.validators.cycle_detection import check_interface_cycle
from lingshu.ontology.validators.dependency import check_delete_dependencies
from lingshu.ontology.validators.immutable import check_immutable_fields

logger = logging.getLogger(__name__)

# Lock configuration
LOCK_TTL_SECONDS = 1800  # 30 minutes
COMMIT_LOCK_TTL_SECONDS = 60

# Entity type → RID type mapping
ENTITY_RID_TYPES: dict[str, str] = {
    "ObjectType": "obj",
    "LinkType": "link",
    "InterfaceType": "iface",
    "SharedPropertyType": "shprop",
    "ActionType": "action",
    "PropertyType": "prop",
}

# Entity type → response class mapping
ENTITY_RESPONSE_MAP: dict[str, type[EntityResponse]] = {
    "ObjectType": ObjectTypeResponse,
    "LinkType": LinkTypeResponse,
    "InterfaceType": InterfaceTypeResponse,
    "SharedPropertyType": SharedPropertyTypeResponse,
    "ActionType": ActionTypeResponse,
}

# JSON-serialized fields for Neo4j storage
_JSON_STORE_FIELDS = frozenset({
    "widget", "validation", "compliance", "parameters", "execution",
    "side_effects", "link_requirements", "object_constraint",
    "asset_mapping", "entity_validation",
})


def _serialize_for_neo4j(props: dict[str, Any]) -> dict[str, Any]:
    """Serialize complex fields to JSON strings for Neo4j storage."""
    result = dict(props)
    for key in _JSON_STORE_FIELDS:
        if key in result and result[key] is not None:
            result[key] = json.dumps(result[key])
    return result


def _deserialize_from_neo4j(props: dict[str, Any]) -> dict[str, Any]:
    """Deserialize JSON string fields from Neo4j to Python objects."""
    result = dict(props)
    for key in _JSON_STORE_FIELDS:
        if key in result and isinstance(result[key], str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                result[key] = json.loads(result[key])
    return result


def _node_to_response(node: dict[str, Any], label: str) -> EntityResponse:
    """Convert a Neo4j node dict to the appropriate response DTO."""
    data = _deserialize_from_neo4j(node)
    response_cls = ENTITY_RESPONSE_MAP.get(label, EntityResponse)

    # Determine version_status
    if data.get("is_draft"):
        version_status = "draft"
    elif data.get("is_staging"):
        version_status = "staging"
    else:
        version_status = "active"
    data["version_status"] = version_status

    # Filter to only fields the response class accepts
    valid_fields = set(response_cls.model_fields.keys())
    filtered = {k: v for k, v in data.items() if k in valid_fields}
    return response_cls(**filtered)


def _node_to_property_response(node: dict[str, Any]) -> PropertyTypeResponse:
    """Convert a Neo4j PropertyType node to response DTO."""
    data = _deserialize_from_neo4j(node)
    valid_fields = set(PropertyTypeResponse.model_fields.keys())
    filtered = {k: v for k, v in data.items() if k in valid_fields}
    return PropertyTypeResponse(**filtered)


class OntologyServiceImpl:
    """Ontology service implementation."""

    def __init__(
        self,
        graph_repo: GraphRepository,
        redis: Redis,
    ) -> None:
        self._graph = graph_repo
        self._redis = redis

    # ── Generic CRUD helpers ──────────────────────────────────────

    async def _create_entity(
        self,
        entity_type: str,
        label: str,
        props: dict[str, Any],
    ) -> EntityResponse:
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        # Check api_name uniqueness
        api_name = props.get("api_name", "")
        is_unique = await self._graph.check_api_name_unique(
            label, api_name, tenant_id
        )
        if not is_unique:
            raise AppError(
                code=ErrorCode.ONTOLOGY_DUPLICATE_API_NAME,
                message=f"api_name '{api_name}' already exists for {label}",
            )

        rid = generate_rid(ENTITY_RID_TYPES[label])
        now = datetime.utcnow().isoformat()

        node_props = _serialize_for_neo4j({
            **props,
            "rid": rid,
            "tenant_id": tenant_id,
            "is_draft": True,
            "is_staging": False,
            "is_active": True,
            "snapshot_id": None,
            "parent_snapshot_id": None,
            "draft_owner": user_id,
            "created_at": now,
            "updated_at": now,
        })

        node = await self._graph.create_node(label, node_props)
        return _node_to_response(node, label)

    async def _get_entity(
        self,
        label: str,
        rid: str,
    ) -> EntityResponse:
        tenant_id = get_tenant_id()
        node = await self._graph.get_active_node(label, rid, tenant_id)
        if not node:
            raise AppError(
                code=ErrorCode.ONTOLOGY_NOT_FOUND,
                message=f"{label} {rid} not found",
            )
        response = _node_to_response(node, label)
        # Populate property_types for ObjectType and LinkType
        if label in ("ObjectType", "LinkType"):
            pt_nodes = await self._graph.get_related_nodes(
                label, rid, tenant_id, "BELONGS_TO", direction="incoming"
            )
            prop_responses = [_node_to_property_response(n) for n in pt_nodes]
            response.property_types = prop_responses
        return response

    async def _get_entity_draft(
        self,
        label: str,
        rid: str,
    ) -> EntityResponse:
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        node = await self._graph.get_effective_node(
            label, rid, tenant_id, user_id
        )
        if not node:
            raise AppError(
                code=ErrorCode.ONTOLOGY_NOT_FOUND,
                message=f"{label} {rid} not found",
            )
        return _node_to_response(node, label)

    async def _update_entity(
        self,
        label: str,
        rid: str,
        updates: dict[str, Any],
    ) -> EntityResponse:
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        # Check lock
        await self._require_lock(rid, user_id)

        # Check immutable fields
        check_immutable_fields(label, updates)

        # Get or create Draft
        draft = await self._graph.get_draft_node(label, rid, tenant_id, user_id)
        if not draft:
            # Clone from Active/Staging to create Draft
            source = await self._graph.get_staging_node(label, rid, tenant_id)
            if not source:
                source = await self._graph.get_active_node(label, rid, tenant_id)
            if not source:
                raise AppError(
                    code=ErrorCode.ONTOLOGY_NOT_FOUND,
                    message=f"{label} {rid} not found",
                )
            # Create Draft as clone
            draft_props = dict(source)
            draft_props["is_draft"] = True
            draft_props["is_staging"] = False
            draft_props["draft_owner"] = user_id
            draft_props["parent_snapshot_id"] = source.get("snapshot_id")
            draft_props.update(_serialize_for_neo4j(updates))
            draft_props["updated_at"] = datetime.utcnow().isoformat()
            node = await self._graph.create_node(label, draft_props)
        else:
            # Update existing Draft
            update_props = _serialize_for_neo4j(updates)
            update_props["updated_at"] = datetime.utcnow().isoformat()
            updated = await self._graph.update_node(
                label, rid, tenant_id, update_props,
                is_draft=True, draft_owner=user_id
            )
            if not updated:
                raise AppError(
                    code=ErrorCode.ONTOLOGY_NOT_FOUND,
                    message=f"Draft for {label} {rid} not found",
                )
            node = updated

        return _node_to_response(node, label)

    async def _delete_entity(
        self,
        label: str,
        rid: str,
    ) -> None:
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        # Check dependencies
        await check_delete_dependencies(self._graph, label, rid, tenant_id)

        # Check lock
        await self._require_lock(rid, user_id)

        # Create Draft deletion marker
        active = await self._graph.get_active_node(label, rid, tenant_id)
        if active:
            # Create Draft with is_active=false (deletion marker)
            draft_props = dict(active)
            draft_props["is_draft"] = True
            draft_props["is_staging"] = False
            draft_props["is_active"] = False
            draft_props["draft_owner"] = user_id
            draft_props["parent_snapshot_id"] = active.get("snapshot_id")
            draft_props["updated_at"] = datetime.utcnow().isoformat()
            await self._graph.create_node(label, draft_props)
        else:
            # If only Draft/Staging exists, just delete it
            deleted = await self._graph.delete_node(
                label, rid, tenant_id, is_draft=True, draft_owner=user_id
            )
            if not deleted:
                await self._graph.delete_node(
                    label, rid, tenant_id, is_staging=True
                )

    async def _query_entities(
        self,
        label: str,
        *,
        search: str | None = None,
        lifecycle_status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[EntityResponse], int]:
        tenant_id = get_tenant_id()
        filters: dict[str, Any] = {}
        if lifecycle_status:
            filters["lifecycle_status"] = lifecycle_status

        nodes, total = await self._graph.list_nodes(
            label, tenant_id,
            offset=offset, limit=limit,
            filters=filters if filters else None,
            search=search,
        )
        responses = [_node_to_response(n, label) for n in nodes]
        # Populate property_types for ObjectType and LinkType
        if label in ("ObjectType", "LinkType"):
            for resp in responses:
                pt_nodes = await self._graph.get_related_nodes(
                    label, resp.rid, tenant_id, "BELONGS_TO", direction="incoming"
                )
                resp.property_types = [_node_to_property_response(n) for n in pt_nodes]
        return responses, total

    # ── Entity-specific CRUD ──────────────────────────────────────

    async def create_object_type(self, props: dict[str, Any]) -> EntityResponse:
        return await self._create_entity("object_type", "ObjectType", props)

    async def create_link_type(self, props: dict[str, Any]) -> EntityResponse:
        return await self._create_entity("link_type", "LinkType", props)

    async def create_interface_type(self, props: dict[str, Any]) -> EntityResponse:
        # Cycle check for EXTENDS
        extends_rids = props.get("extends_interface_type_rids", [])
        if extends_rids:
            rid = props.get("rid", "new")
            await check_interface_cycle(
                self._graph, rid, extends_rids, get_tenant_id()
            )
        return await self._create_entity("interface_type", "InterfaceType", props)

    async def create_shared_property_type(self, props: dict[str, Any]) -> EntityResponse:
        return await self._create_entity(
            "shared_property_type", "SharedPropertyType", props
        )

    async def create_action_type(self, props: dict[str, Any]) -> EntityResponse:
        return await self._create_entity("action_type", "ActionType", props)

    async def get_object_type(self, rid: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        tid = tenant_id or get_tenant_id()
        return await self._graph.get_active_node("ObjectType", rid, tid)

    async def get_link_type(self, rid: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        tid = tenant_id or get_tenant_id()
        return await self._graph.get_active_node("LinkType", rid, tid)

    async def update_object_type(self, rid: str, updates: dict[str, Any]) -> EntityResponse:
        return await self._update_entity("ObjectType", rid, updates)

    async def update_link_type(self, rid: str, updates: dict[str, Any]) -> EntityResponse:
        return await self._update_entity("LinkType", rid, updates)

    async def update_interface_type(self, rid: str, updates: dict[str, Any]) -> EntityResponse:
        tenant_id = get_tenant_id()
        # Cycle check if extends changed
        extends_rids = updates.get("extends_interface_type_rids")
        if extends_rids:
            await check_interface_cycle(
                self._graph, rid, extends_rids, tenant_id
            )
        # Contract validation if required_shared_property_type_rids changed
        required_rids = updates.get("required_shared_property_type_rids")
        if required_rids is not None:
            await check_contract_satisfaction(
                self._graph, rid, tenant_id, required_rids
            )
        return await self._update_entity("InterfaceType", rid, updates)

    async def update_shared_property_type(
        self, rid: str, updates: dict[str, Any]
    ) -> EntityResponse:
        tenant_id = get_tenant_id()
        # Fetch old values before update for cascade value comparison
        old_node = await self._graph.get_active_node(
            "SharedPropertyType", rid, tenant_id
        )
        old_values = _deserialize_from_neo4j(old_node) if old_node else {}

        result = await self._update_entity("SharedPropertyType", rid, updates)
        # Cascade updates to inheriting PropertyTypes with old value comparison
        await cascade_shared_property_update(
            self._graph, rid, tenant_id, updates, old_values=old_values
        )
        return result

    async def update_action_type(self, rid: str, updates: dict[str, Any]) -> EntityResponse:
        return await self._update_entity("ActionType", rid, updates)

    async def delete_object_type(self, rid: str) -> None:
        await self._delete_entity("ObjectType", rid)

    async def delete_link_type(self, rid: str) -> None:
        await self._delete_entity("LinkType", rid)

    async def delete_interface_type(self, rid: str) -> None:
        await self._delete_entity("InterfaceType", rid)

    async def delete_shared_property_type(self, rid: str) -> None:
        await self._delete_entity("SharedPropertyType", rid)

    async def delete_action_type(self, rid: str) -> None:
        await self._delete_entity("ActionType", rid)

    async def query_action_types(
        self, tenant_id: str, *, offset: int = 0, limit: int = 1000
    ) -> tuple[list[dict[str, Any]], int]:
        """Query active ActionType entities for a tenant."""
        return await self._graph.list_active_nodes(
            "ActionType", tenant_id, offset=offset, limit=limit,
        )

    # ── PropertyType CRUD ─────────────────────────────────────────

    async def create_property_type(
        self,
        parent_rid: str,
        parent_label: str,
        props: dict[str, Any],
    ) -> PropertyTypeResponse:
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        await self._require_lock(parent_rid, user_id)

        # Check for duplicate api_name within parent
        api_name = props.get("api_name", "")
        existing_pts = await self._graph.get_related_nodes(
            parent_label, parent_rid, tenant_id, "BELONGS_TO", direction="incoming"
        )
        for pt in existing_pts:
            if pt.get("api_name") == api_name:
                raise AppError(
                    code=ErrorCode.ONTOLOGY_DUPLICATE_API_NAME,
                    message=f"PropertyType '{api_name}' already exists on {parent_label} {parent_rid}",
                )

        rid = generate_rid("prop")
        now = datetime.utcnow().isoformat()
        node_props = _serialize_for_neo4j({
            **props,
            "rid": rid,
            "tenant_id": tenant_id,
            "is_draft": True,
            "is_staging": False,
            "is_active": True,
            "draft_owner": user_id,
            "created_at": now,
            "updated_at": now,
        })

        node = await self._graph.create_node("PropertyType", node_props)

        # Create BELONGS_TO relationship
        await self._graph.create_relationship(
            "PropertyType", rid, parent_label, parent_rid,
            "BELONGS_TO", tenant_id,
        )

        # Create BASED_ON relationship if inheriting
        inherit_rid = props.get("inherit_from_shared_property_type_rid")
        if inherit_rid:
            await self._graph.create_relationship(
                "PropertyType", rid, "SharedPropertyType", inherit_rid,
                "BASED_ON", tenant_id,
            )

        return _node_to_property_response(node)

    async def get_property_types_for_entity(
        self,
        entity_rid: str,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        tid = tenant_id or get_tenant_id()
        # PropertyTypes connected via BELONGS_TO (incoming to parent)
        nodes = await self._graph.get_related_nodes(
            "ObjectType", entity_rid, tid, "BELONGS_TO", direction="incoming"
        )
        if not nodes:
            nodes = await self._graph.get_related_nodes(
                "LinkType", entity_rid, tid, "BELONGS_TO", direction="incoming"
            )
        return [_deserialize_from_neo4j(n) for n in nodes]

    async def get_asset_mapping(
        self, entity_rid: str, tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        tid = tenant_id or get_tenant_id()
        # Try ObjectType first
        node = await self._graph.get_active_node("ObjectType", entity_rid, tid)
        if not node:
            node = await self._graph.get_active_node("LinkType", entity_rid, tid)
        if not node:
            return None
        data = _deserialize_from_neo4j(node)
        return data.get("asset_mapping")

    # ── Lock Management ───────────────────────────────────────────

    async def acquire_lock(self, rid: str) -> LockStatusResponse:
        user_id = get_user_id()
        lock_key = f"ontology:lock:{rid}"

        # Try to set lock with NX (only if not exists)
        acquired = await self._redis.set(
            lock_key, user_id, nx=True, ex=LOCK_TTL_SECONDS
        )

        if not acquired:
            # Check who owns the lock
            owner = await self._redis.get(lock_key)
            owner_str = owner.decode() if isinstance(owner, bytes) else str(owner) if owner else None
            if owner_str == user_id:
                # Already own it, refresh TTL
                await self._redis.expire(lock_key, LOCK_TTL_SECONDS)
                return LockStatusResponse(
                    rid=rid, locked=True, locked_by=user_id,
                    expires_in=LOCK_TTL_SECONDS,
                )
            raise AppError(
                code=ErrorCode.ONTOLOGY_LOCK_CONFLICT,
                message=f"Entity {rid} is locked by another user",
                details={"locked_by": owner_str},
            )

        return LockStatusResponse(
            rid=rid, locked=True, locked_by=user_id,
            expires_in=LOCK_TTL_SECONDS,
        )

    async def release_lock(self, rid: str) -> LockStatusResponse:
        user_id = get_user_id()
        lock_key = f"ontology:lock:{rid}"

        owner = await self._redis.get(lock_key)
        owner_str = owner.decode() if isinstance(owner, bytes) else str(owner) if owner else None
        if owner_str == user_id:
            await self._redis.delete(lock_key)

        return LockStatusResponse(rid=rid, locked=False)

    async def refresh_lock(self, rid: str) -> LockStatusResponse:
        user_id = get_user_id()
        lock_key = f"ontology:lock:{rid}"

        owner = await self._redis.get(lock_key)
        owner_str = owner.decode() if isinstance(owner, bytes) else str(owner) if owner else None
        if owner_str != user_id:
            raise AppError(
                code=ErrorCode.ONTOLOGY_LOCK_CONFLICT,
                message=f"You don't own the lock on {rid}",
            )

        await self._redis.expire(lock_key, LOCK_TTL_SECONDS)
        ttl = await self._redis.ttl(lock_key)
        return LockStatusResponse(
            rid=rid, locked=True, locked_by=user_id, expires_in=ttl,
        )

    async def _require_lock(self, rid: str, user_id: str) -> None:
        """Verify that the user holds the lock on the entity."""
        lock_key = f"ontology:lock:{rid}"
        owner = await self._redis.get(lock_key)
        owner_str = owner.decode() if isinstance(owner, bytes) else str(owner) if owner else None
        if owner_str != user_id:
            raise AppError(
                code=ErrorCode.ONTOLOGY_LOCK_REQUIRED,
                message=f"Lock required on {rid}. Acquire lock first.",
            )

    # ── Submit to Staging ─────────────────────────────────────────

    async def submit_to_staging(self, label: str, rid: str) -> EntityResponse:
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        draft = await self._graph.get_draft_node(label, rid, tenant_id, user_id)
        if not draft:
            raise AppError(
                code=ErrorCode.ONTOLOGY_DRAFT_NOT_FOUND,
                message=f"No Draft found for {label} {rid}",
            )

        # Update Draft → Staging
        update_props = {
            "is_draft": False,
            "is_staging": True,
            "draft_owner": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
        node = await self._graph.update_node(
            label, rid, tenant_id, update_props,
            is_draft=True, draft_owner=user_id,
        )
        if not node:
            raise AppError(
                code=ErrorCode.ONTOLOGY_DRAFT_NOT_FOUND,
                message=f"Failed to promote Draft for {label} {rid}",
            )

        # Release lock
        lock_key = f"ontology:lock:{rid}"
        await self._redis.delete(lock_key)

        return _node_to_response(node, label)

    async def discard_draft(self, label: str, rid: str) -> None:
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        deleted = await self._graph.delete_node(
            label, rid, tenant_id, is_draft=True, draft_owner=user_id
        )
        if not deleted:
            raise AppError(
                code=ErrorCode.ONTOLOGY_DRAFT_NOT_FOUND,
                message=f"No Draft found for {label} {rid}",
            )

        # Release lock
        lock_key = f"ontology:lock:{rid}"
        await self._redis.delete(lock_key)

    async def discard_staging(self, label: str, rid: str) -> None:
        tenant_id = get_tenant_id()

        # Check if Active exists
        active = await self._graph.get_active_node(label, rid, tenant_id)
        if active:
            # Just delete the Staging node
            deleted = await self._graph.delete_node(
                label, rid, tenant_id, is_staging=True
            )
            if not deleted:
                raise AppError(
                    code=ErrorCode.ONTOLOGY_STAGING_NOT_FOUND,
                    message=f"No Staging found for {label} {rid}",
                )
        else:
            # No Active — convert Staging back to Draft
            staging = await self._graph.get_staging_node(label, rid, tenant_id)
            if not staging:
                raise AppError(
                    code=ErrorCode.ONTOLOGY_STAGING_NOT_FOUND,
                    message=f"No Staging found for {label} {rid}",
                )
            user_id = get_user_id()
            await self._graph.update_node(
                label, rid, tenant_id,
                {
                    "is_staging": False,
                    "is_draft": True,
                    "draft_owner": user_id,
                },
            )

    # ── Staging Summary & Commit ──────────────────────────────────

    async def get_staging_summary(self) -> StagingSummaryResponse:
        tenant_id = get_tenant_id()
        counts = await self._graph.get_staging_summary(tenant_id)
        total = sum(counts.values())
        return StagingSummaryResponse(counts=counts, total=total)

    async def get_drafts_summary(self) -> DraftsSummaryResponse:
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        counts = await self._graph.get_drafts_summary(tenant_id, user_id)
        total = sum(counts.values())
        return DraftsSummaryResponse(counts=counts, total=total)

    async def commit_staging(
        self,
        commit_message: str | None,
        session: AsyncSession,
    ) -> SnapshotResponse:
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        # Acquire tenant-level commit lock
        commit_lock_key = f"ontology:commit_lock:{tenant_id}"
        acquired = await self._redis.set(
            commit_lock_key, user_id, nx=True, ex=COMMIT_LOCK_TTL_SECONDS
        )
        if not acquired:
            raise AppError(
                code=ErrorCode.ONTOLOGY_LOCK_CONFLICT,
                message="Another commit is in progress",
            )

        try:
            # Get staging nodes
            staging_nodes = await self._graph.get_staging_nodes(tenant_id)
            if not staging_nodes:
                raise AppError(
                    code=ErrorCode.ONTOLOGY_STAGING_EMPTY,
                    message="No entities in Staging to publish",
                )

            # Build entity_changes
            entity_changes: dict[str, str] = {}
            for node in staging_nodes:
                node_rid = node.get("rid", "")
                if node.get("is_active"):
                    # Check if Active exists → update, else create
                    label = node.get("_label", "")
                    active = await self._graph.get_active_node(
                        label, node_rid, tenant_id
                    )
                    entity_changes[node_rid] = "update" if active else "create"
                else:
                    entity_changes[node_rid] = "delete"

            # Create snapshot
            snapshot_id = generate_rid("snap")
            snap_repo = SnapshotRepository(session)

            # Get current active pointer for parent_snapshot_id
            pointer = await snap_repo.get_active_pointer(tenant_id)
            parent_snapshot_id = pointer.snapshot_id if pointer else None

            # Build entity_data for field-level diff support
            entity_data: dict[str, dict[str, Any]] = {}
            for node in staging_nodes:
                node_rid = node.get("rid", "")
                if node_rid:
                    # Store deserialized node data (exclude internal fields)
                    node_data = _deserialize_from_neo4j(node)
                    entity_data[node_rid] = {
                        k: v for k, v in node_data.items()
                        if not k.startswith("_")
                    }

            snapshot = Snapshot(
                snapshot_id=snapshot_id,
                parent_snapshot_id=parent_snapshot_id,
                tenant_id=tenant_id,
                commit_message=commit_message,
                author=user_id,
                entity_changes=entity_changes,
                entity_data=entity_data,
            )
            await snap_repo.create(snapshot)

            # Promote Staging → Active in Neo4j (with retry for transient failures)
            await retry_neo4j_operation(
                lambda: self._graph.promote_staging_to_active(tenant_id, snapshot_id)
            )

            # Update active pointer
            await snap_repo.set_active_pointer(tenant_id, snapshot_id)

            await session.commit()

            # Notify schema published (cache invalidation + pub/sub)
            await self.on_schema_published(tenant_id, snapshot_id, session)

            return SnapshotResponse(
                snapshot_id=snapshot_id,
                parent_snapshot_id=parent_snapshot_id,
                tenant_id=tenant_id,
                commit_message=commit_message,
                author=user_id,
                entity_changes=entity_changes,
                created_at=datetime.utcnow().isoformat(),
            )
        finally:
            await self._redis.delete(commit_lock_key)

    async def discard_all_staging(self) -> int:
        """Discard all Staging entities. Returns count discarded."""
        tenant_id = get_tenant_id()
        staging_nodes = await self._graph.get_staging_nodes(tenant_id)
        count = 0
        for node in staging_nodes:
            label = node.get("_label", "")
            rid = node.get("rid", "")
            if label and rid:
                await self._graph.delete_node(
                    label, rid, tenant_id, is_staging=True
                )
                count += 1
        return count

    # ── Snapshots ─────────────────────────────────────────────────

    async def query_snapshots(
        self, session: AsyncSession, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[SnapshotResponse], int]:
        tenant_id = get_tenant_id()
        repo = SnapshotRepository(session)
        snapshots, total = await repo.list_by_tenant(
            tenant_id, offset=offset, limit=limit
        )
        responses = [
            SnapshotResponse(
                snapshot_id=s.snapshot_id,
                parent_snapshot_id=s.parent_snapshot_id,
                tenant_id=s.tenant_id,
                commit_message=s.commit_message,
                author=s.author,
                entity_changes=s.entity_changes,
                created_at=s.created_at.isoformat() if s.created_at else None,
            )
            for s in snapshots
        ]
        return responses, total

    async def get_snapshot(
        self, snapshot_id: str, session: AsyncSession,
    ) -> SnapshotResponse:
        repo = SnapshotRepository(session)
        snap = await repo.get_by_id(snapshot_id)
        if not snap:
            raise AppError(
                code=ErrorCode.ONTOLOGY_NOT_FOUND,
                message=f"Snapshot {snapshot_id} not found",
            )
        return SnapshotResponse(
            snapshot_id=snap.snapshot_id,
            parent_snapshot_id=snap.parent_snapshot_id,
            tenant_id=snap.tenant_id,
            commit_message=snap.commit_message,
            author=snap.author,
            entity_changes=snap.entity_changes,
            created_at=snap.created_at.isoformat() if snap.created_at else None,
        )

    async def get_snapshot_diff(
        self, snapshot_id: str, session: AsyncSession,
    ) -> SnapshotDiffResponse:
        tenant_id = get_tenant_id()
        repo = SnapshotRepository(session)
        pointer = await repo.get_active_pointer(tenant_id)
        current_id = pointer.snapshot_id if pointer else None
        diff = await repo.get_diff(snapshot_id, current_id)
        return SnapshotDiffResponse(**diff)

    async def rollback_to_snapshot(
        self, snapshot_id: str, session: AsyncSession,
    ) -> SnapshotResponse:
        tenant_id = get_tenant_id()

        # Check for uncommitted changes
        has_changes = await self._graph.has_uncommitted_changes(tenant_id)
        if has_changes:
            raise AppError(
                code=ErrorCode.ONTOLOGY_UNCOMMITTED_CHANGES,
                message="Cannot rollback with uncommitted Draft/Staging changes",
            )

        repo = SnapshotRepository(session)
        snap = await repo.get_by_id(snapshot_id)
        if not snap:
            raise AppError(
                code=ErrorCode.ONTOLOGY_NOT_FOUND,
                message=f"Snapshot {snapshot_id} not found",
            )

        pointer = await repo.get_active_pointer(tenant_id)
        current_id = pointer.snapshot_id if pointer else ""

        # Rollback in Neo4j
        await self._graph.rollback_to_snapshot(
            tenant_id, snapshot_id, current_id
        )

        # Update active pointer
        await repo.set_active_pointer(tenant_id, snapshot_id)
        await session.commit()

        return SnapshotResponse(
            snapshot_id=snap.snapshot_id,
            parent_snapshot_id=snap.parent_snapshot_id,
            tenant_id=snap.tenant_id,
            commit_message=snap.commit_message,
            author=snap.author,
            entity_changes=snap.entity_changes,
            created_at=snap.created_at.isoformat() if snap.created_at else None,
        )

    # ── Topology & Search ─────────────────────────────────────────

    async def get_topology(self) -> TopologyResponse:
        tenant_id = get_tenant_id()
        data = await self._graph.get_topology(tenant_id)
        return TopologyResponse(**data)

    async def search(
        self,
        query: str,
        *,
        types: list[str] | None = None,
        limit: int = 20,
    ) -> list[SearchResultResponse]:
        tenant_id = get_tenant_id()
        labels = None
        if types:
            labels = [ENTITY_LABELS.get(t, t) for t in types]

        nodes = await self._graph.search_nodes(
            tenant_id, query, labels=labels, limit=limit
        )
        return [
            SearchResultResponse(
                rid=n.get("rid", ""),
                api_name=n.get("api_name", ""),
                display_name=n.get("display_name", ""),
                description=n.get("description"),
                entity_type=n.get("_entity_type", ""),
            )
            for n in nodes
        ]

    # ── Related entities ──────────────────────────────────────────

    async def get_related(
        self, label: str, rid: str,
    ) -> list[dict[str, Any]]:
        tenant_id = get_tenant_id()
        # Get all relationships (both directions)
        outgoing = await self._graph.get_related_nodes(
            label, rid, tenant_id, "", direction="both"
        )
        return [_deserialize_from_neo4j(n) for n in outgoing]

    # ── on_schema_published (Protocol implementation) ─────────────

    async def on_schema_published(
        self, tenant_id: str, snapshot_id: str, session: AsyncSession,
    ) -> None:
        """Handle schema publication: invalidate caches and notify subscribers.

        1. Delete cached schema keys for the tenant.
        2. Publish a notification on the schema_published Redis channel.
        """
        # Invalidate cached schema data for this tenant
        cache_pattern = f"ontology:cache:{tenant_id}:*"
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor, match=cache_pattern, count=100
            )
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break

        # Publish notification via Redis Pub/Sub
        message = json.dumps({
            "tenant_id": tenant_id,
            "snapshot_id": snapshot_id,
            "event": "schema_published",
        })
        await self._redis.publish(
            f"ontology:schema_published:{tenant_id}",
            message,
        )
        logger.info(
            "Schema published: tenant=%s, snapshot=%s",
            tenant_id,
            snapshot_id,
        )

    # ── AssetMapping queries ─────────────────────────────────────

    async def query_asset_mapping_references(
        self,
        entity_rid: str,
    ) -> list[dict[str, Any]]:
        """Query all entities that reference the given entity's asset mapping.

        Returns list of PropertyTypes/entities that reference this asset mapping.
        """
        tenant_id = get_tenant_id()

        # Get the entity to check it exists
        node = await self._graph.get_active_node("ObjectType", entity_rid, tenant_id)
        if not node:
            node = await self._graph.get_active_node("LinkType", entity_rid, tenant_id)
        if not node:
            raise AppError(
                code=ErrorCode.ONTOLOGY_NOT_FOUND,
                message=f"Entity {entity_rid} not found",
            )

        # Get PropertyTypes belonging to this entity
        pt_nodes = await self._graph.get_related_nodes(
            "ObjectType" if entity_rid.startswith("ri.obj.") else "LinkType",
            entity_rid,
            tenant_id,
            "BELONGS_TO",
            direction="incoming",
        )

        references: list[dict[str, Any]] = []
        for pt in pt_nodes:
            pt_data = _deserialize_from_neo4j(pt)
            if pt_data.get("physical_column"):
                references.append({
                    "rid": pt_data.get("rid", ""),
                    "api_name": pt_data.get("api_name", ""),
                    "physical_column": pt_data.get("physical_column"),
                    "entity_rid": entity_rid,
                })

        return references

    # ── Independent queries (PropertyType / AssetMapping) ─────────

    async def query_all_property_types(
        self,
        *,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[PropertyTypeResponse], int]:
        """Query all PropertyTypes across all parent entities."""
        tenant_id = get_tenant_id()
        nodes, total = await self._graph.list_active_nodes(
            "PropertyType",
            tenant_id,
            offset=offset,
            limit=limit,
            search=search,
        )
        responses = [_node_to_property_response(n) for n in nodes]
        return responses, total

    async def query_all_asset_mappings(
        self,
        *,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Query all ObjectTypes/LinkTypes that have asset_mapping configured."""
        tenant_id = get_tenant_id()

        # Query ObjectTypes with asset_mapping
        obj_nodes, obj_total = await self._graph.list_active_nodes(
            "ObjectType", tenant_id, offset=0, limit=1000, search=search,
        )
        link_nodes, link_total = await self._graph.list_active_nodes(
            "LinkType", tenant_id, offset=0, limit=1000, search=search,
        )

        all_nodes = obj_nodes + link_nodes
        results: list[dict[str, Any]] = []
        for node in all_nodes:
            data = _deserialize_from_neo4j(node)
            if data.get("asset_mapping"):
                results.append({
                    "rid": data.get("rid", ""),
                    "api_name": data.get("api_name", ""),
                    "display_name": data.get("display_name", ""),
                    "asset_mapping": data["asset_mapping"],
                    "entity_type": "ObjectType" if data.get("rid", "").startswith("ri.obj.") else "LinkType",
                })

        total = len(results)
        paginated = results[offset:offset + limit]
        return paginated, total
