"""Workflow service: CRUD + execution for workflows."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.function.models import Workflow
from lingshu.function.schemas.responses import (
    WorkflowEdgeResponse,
    WorkflowExecutionResponse,
    WorkflowNodeResponse,
    WorkflowResponse,
)
from lingshu.function.workflows.engine import WorkflowEngine
from lingshu.function.workflows.models import WorkflowDefinition
from lingshu.function.workflows.repository import WorkflowRepository, recompute_safety_level
from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode


class WorkflowService:
    """Workflow management and execution."""

    def __init__(self) -> None:
        self._engine = WorkflowEngine()

    async def create_workflow(
        self,
        api_name: str,
        display_name: str,
        description: str | None,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        status: str,
        session: AsyncSession,
    ) -> WorkflowResponse:
        tenant_id = get_tenant_id()
        rid = f"ri.workflow.{uuid.uuid4().hex[:12]}"

        definition = {"nodes": nodes, "edges": edges}
        safety = recompute_safety_level(definition)

        workflow = Workflow(
            rid=rid,
            tenant_id=tenant_id,
            api_name=api_name,
            display_name=display_name,
            description=description,
            parameters=[],
            definition=definition,
            safety_level=safety,
            side_effects=[],
        )

        repo = WorkflowRepository(session)
        await repo.create(workflow)
        await session.commit()

        return self._to_response(workflow)

    async def get_workflow(
        self, rid: str, session: AsyncSession,
    ) -> WorkflowResponse:
        tenant_id = get_tenant_id()
        repo = WorkflowRepository(session)
        workflow = await repo.get_by_rid(rid, tenant_id)
        if not workflow:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Workflow {rid} not found",
            )
        return self._to_response(workflow)

    async def update_workflow(
        self, rid: str, updates: dict[str, Any], session: AsyncSession,
    ) -> WorkflowResponse:
        tenant_id = get_tenant_id()
        repo = WorkflowRepository(session)
        workflow = await repo.get_by_rid(rid, tenant_id)
        if not workflow:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Workflow {rid} not found",
            )

        fields: dict[str, Any] = {}

        if "display_name" in updates:
            fields["display_name"] = updates["display_name"]
        if "description" in updates:
            fields["description"] = updates["description"]
        if "status" in updates:
            # Store status in the is_active field: active=True, otherwise False
            fields["is_active"] = updates["status"] == "active"

        # If nodes or edges changed, rebuild the definition
        if "nodes" in updates or "edges" in updates:
            current_def = workflow.definition or {}
            new_nodes = updates.get("nodes", current_def.get("nodes", []))
            new_edges = updates.get("edges", current_def.get("edges", []))
            definition = {"nodes": new_nodes, "edges": new_edges}
            fields["definition"] = definition
            fields["safety_level"] = recompute_safety_level(definition)

        updated = await repo.update_fields(rid, tenant_id, **fields)
        await session.commit()

        if not updated:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Workflow {rid} not found after update",
            )
        return self._to_response(updated)

    async def delete_workflow(
        self, rid: str, session: AsyncSession,
    ) -> None:
        tenant_id = get_tenant_id()
        repo = WorkflowRepository(session)
        deleted = await repo.delete(rid, tenant_id)
        if not deleted:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Workflow {rid} not found",
            )
        await session.commit()

    async def query_workflows(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
    ) -> tuple[list[WorkflowResponse], int]:
        tenant_id = get_tenant_id()
        repo = WorkflowRepository(session)
        workflows, total = await repo.list_by_tenant(
            tenant_id, offset=offset, limit=limit, status=status,
        )
        return [self._to_response(wf) for wf in workflows], total

    async def execute_workflow(
        self,
        rid: str,
        inputs: dict[str, Any],
        session: AsyncSession,
    ) -> WorkflowExecutionResponse:
        tenant_id = get_tenant_id()
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"

        repo = WorkflowRepository(session)
        workflow = await repo.get_by_rid(rid, tenant_id)
        if not workflow:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Workflow {rid} not found",
            )

        definition = WorkflowDefinition.model_validate(
            workflow.definition or {},
        )

        started_at = datetime.now(tz=UTC)
        result = await self._engine.execute(definition, inputs)
        completed_at = datetime.now(tz=UTC)

        return WorkflowExecutionResponse(
            execution_id=execution_id,
            workflow_rid=rid,
            status=result.get("status", "success"),
            steps=result.get("steps", []),
            outputs=result.get("outputs", {}),
            started_at=started_at,
            completed_at=completed_at,
        )

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _to_response(workflow: Workflow) -> WorkflowResponse:
        definition = workflow.definition or {}
        nodes_raw = definition.get("nodes", [])
        edges_raw = definition.get("edges", [])

        nodes = [
            WorkflowNodeResponse(**n) if isinstance(n, dict) else n
            for n in nodes_raw
        ]
        edges = [
            WorkflowEdgeResponse(**e) if isinstance(e, dict) else e
            for e in edges_raw
        ]

        # Derive status from is_active
        status = "active" if workflow.is_active else "draft"

        return WorkflowResponse(
            rid=workflow.rid,
            api_name=workflow.api_name,
            display_name=workflow.display_name,
            description=workflow.description,
            nodes=nodes,
            edges=edges,
            safety_level=workflow.safety_level,
            status=status,
            version=workflow.version,
            is_active=workflow.is_active,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )
