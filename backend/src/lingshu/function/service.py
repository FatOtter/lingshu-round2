"""Function service: action execution + global function management + capability catalog."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.data.interface import DataService
from lingshu.function.actions.engines.native_crud import NativeCRUDEngine
from lingshu.function.actions.engines.python_venv import PythonVenvEngine
from lingshu.function.actions.engines.sql_runner import SQLRunnerEngine
from lingshu.function.actions.engines.webhook import WebhookEngine
from lingshu.function.actions.loader import ActionLoader
from lingshu.function.actions.param_resolver import ParamResolver
from lingshu.function.audit.logger import AuditLogger
from lingshu.function.globals.builtins import BuiltinFunctions
from lingshu.function.globals.executor import GlobalFunctionExecutor
from lingshu.function.globals.registry import FunctionRegistry
from lingshu.function.repository.execution_repo import ExecutionRepository
from lingshu.function.repository.function_repo import GlobalFunctionRepository
from lingshu.function.safety.enforcer import SafetyEnforcer
from lingshu.function.schemas.responses import (
    CapabilityDescriptor,
    ExecutionDetailResponse,
    ExecutionResponse,
    FunctionOverviewResponse,
    GlobalFunctionResponse,
)
from lingshu.function.workflows.repository import WorkflowRepository
from lingshu.infra.context import get_tenant_id, get_user_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.interface import OntologyService

# Confirmation expiry
CONFIRMATION_TTL = timedelta(minutes=10)

logger = logging.getLogger(__name__)


class FunctionServiceImpl:
    """Function service implementation."""

    def __init__(
        self,
        ontology_service: OntologyService,
        data_service: DataService,
    ) -> None:
        self._ontology = ontology_service
        self._data = data_service
        self._loader = ActionLoader(ontology_service)
        self._param_resolver = ParamResolver(data_service)
        self._safety = SafetyEnforcer()
        self._audit = AuditLogger()
        self._registry = FunctionRegistry()
        self._builtins = BuiltinFunctions(ontology_service, data_service)
        self._executor = GlobalFunctionExecutor(self._builtins)
        self._native_crud = NativeCRUDEngine()
        self._python_venv = PythonVenvEngine()
        self._sql_runner = SQLRunnerEngine()
        self._webhook = WebhookEngine()

    # ── Action Execution ─────────────────────────────────────────

    async def execute_action(
        self,
        action_type_rid: str,
        params: dict[str, Any],
        session: AsyncSession,
        *,
        branch: str | None = None,
        skip_confirmation: bool = False,
    ) -> ExecutionResponse:
        """Execute an action through the full pipeline."""
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"

        # Stage 1: Load action definition
        action_def = await self._loader.load(action_type_rid)

        # Stage 2: Resolve parameters
        resolved = await self._param_resolver.resolve(
            action_def.parameters, params,
        )

        # Stage 3: Safety check
        decision = self._safety.check(
            action_def.safety_level,
            action_def.outputs,
            action_def.side_effects,
            skip_confirmation=skip_confirmation,
        )

        if decision.requires_confirmation:
            # Log as pending
            await self._audit.log_start(
                session,
                execution_id=execution_id,
                tenant_id=tenant_id,
                capability_type="action",
                capability_rid=action_type_rid,
                status="pending_confirmation",
                params=params,
                safety_level=action_def.safety_level,
                side_effects=action_def.side_effects,
                user_id=user_id,
                branch=branch,
            )
            await session.commit()

            return ExecutionResponse(
                execution_id=execution_id,
                status="pending_confirmation",
                confirmation={
                    "message": decision.message,
                    "safety_level": action_def.safety_level,
                    "affected_outputs": decision.affected_outputs,
                    "side_effects": decision.side_effects,
                    "confirm_url": f"/function/v1/executions/{execution_id}/confirm",
                    "cancel_url": f"/function/v1/executions/{execution_id}/cancel",
                },
                started_at=datetime.now(tz=UTC),
            )

        # Stage 4: Engine execution
        engine_result = await self._execute_engine(
            action_def.execution, resolved.values, resolved.instances,
        )

        # Stage 4.5: Writeback
        writeback_results: list[dict[str, Any]] = []
        outputs_config = action_def.outputs
        has_writeback = any(o.get("writeback", False) for o in outputs_config)
        if has_writeback:
            writeback_results = await self._process_writeback(
                outputs_config,
                engine_result,
                resolved.values,
                resolved.instances,
                session,
                user_id=user_id,
                action_type_rid=action_type_rid,
                branch=branch,
            )

        # Stage 5: Log execution
        await self._audit.log_start(
            session,
            execution_id=execution_id,
            tenant_id=tenant_id,
            capability_type="action",
            capability_rid=action_type_rid,
            status="success",
            params=params,
            safety_level=action_def.safety_level,
            side_effects=action_def.side_effects,
            user_id=user_id,
            branch=branch,
        )
        result_data: dict[str, Any] = {
            "data": engine_result.data,
            "computed_values": engine_result.computed_values,
        }
        if writeback_results:
            result_data["writeback"] = writeback_results
        await self._audit.log_complete(
            session,
            execution_id=execution_id,
            tenant_id=tenant_id,
            status="success",
            result=result_data,
            confirmed_by="copilot_interrupt" if skip_confirmation else None,
        )
        await session.commit()

        return ExecutionResponse(
            execution_id=execution_id,
            status="success",
            result=result_data,
            started_at=datetime.now(tz=UTC),
            completed_at=datetime.now(tz=UTC),
        )

    async def _execute_engine(
        self,
        execution_config: dict[str, Any],
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> Any:
        """Dispatch to the appropriate engine."""
        exec_type = execution_config.get("type", "native_crud")

        if exec_type == "native_crud":
            crud_config = execution_config.get("native_crud_json", {})
            return await self._native_crud.execute(
                crud_config, resolved_params, instances,
            )

        if exec_type == "python_venv":
            python_config = execution_config.get("python_script", {})
            return await self._python_venv.execute(
                python_config, resolved_params, instances,
            )

        if exec_type == "sql_runner":
            sql_config = execution_config.get("sql_template", {})
            return await self._sql_runner.execute(
                sql_config, resolved_params, instances,
            )

        if exec_type == "webhook":
            webhook_config = execution_config.get("webhook_config_json", {})
            return await self._webhook.execute(
                webhook_config, resolved_params, instances,
            )

        raise AppError(
            code=ErrorCode.FUNCTION_EXECUTION_FAILED,
            message=f"Unsupported engine type: {exec_type}",
        )

    async def _process_writeback(
        self,
        outputs_config: list[dict[str, Any]],
        engine_result: Any,
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
        session: AsyncSession,
        *,
        user_id: str,
        action_type_rid: str,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        """Process outputs with writeback=true, writing edit logs via DataService."""
        writeback_results: list[dict[str, Any]] = []

        # Check if data service supports write_editlog
        if not hasattr(self._data, "write_editlog"):
            logger.warning(
                "DataService does not have write_editlog method; skipping writeback"
            )
            return writeback_results

        for output in outputs_config:
            if not output.get("writeback", False):
                continue

            target_param = output.get("target_param", "")
            operation = output.get("operation", "update")
            output_name = output.get("name", "")

            # Get the computed field values from engine result
            computed = engine_result.computed_values.get(output_name, {})

            # Get target instance's type_rid and primary_key from resolved params
            instance = instances.get(target_param)
            if not instance:
                continue

            type_rid = instance.get("_type_rid", "")
            primary_key = instance.get("_primary_key", {})

            # Write to DataService
            entry_id = await self._data.write_editlog(
                type_rid=type_rid,
                primary_key=primary_key,
                operation=operation,
                field_values=computed,
                user_id=user_id,
                session=session,
                action_type_rid=action_type_rid,
                branch=branch or "main",
            )

            writeback_results.append({
                "output": output_name,
                "entry_id": entry_id,
                "operation": operation,
                "target_param": target_param,
            })

        return writeback_results

    # ── Batch Execution ──────────────────────────────────────────

    async def execute_action_batch(
        self,
        action_type_rid: str,
        batch_params: list[dict[str, Any]],
        session: AsyncSession,
        *,
        branch: str | None = None,
        skip_confirmation: bool = False,
    ) -> dict[str, Any]:
        """Execute an action for each item in batch_params.

        Returns summary with success_count, failure_count, and per-item results.
        Non-transactional: each item executed independently.
        """
        results: list[dict[str, Any]] = []
        success_count = 0
        failure_count = 0

        for i, params in enumerate(batch_params):
            try:
                result = await self.execute_action(
                    action_type_rid, params, session,
                    branch=branch, skip_confirmation=skip_confirmation,
                )
                results.append({
                    "index": i,
                    "status": result.status,
                    "execution_id": result.execution_id,
                })
                if result.status == "success":
                    success_count += 1
                else:
                    failure_count += 1
            except AppError as e:
                results.append({"index": i, "status": "failed", "error": e.message})
                failure_count += 1

        return {
            "total": len(batch_params),
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results,
        }

    # ── Async Execution ──────────────────────────────────────────

    async def execute_action_async(
        self,
        action_type_rid: str,
        params: dict[str, Any],
        session: AsyncSession,
        *,
        branch: str | None = None,
        skip_confirmation: bool = False,
    ) -> ExecutionResponse:
        """Start an action execution asynchronously.

        Returns immediately with execution_id and status='running'.
        The actual execution runs in the background.
        """
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"

        # Log as running
        await self._audit.log_start(
            session,
            execution_id=execution_id,
            tenant_id=tenant_id,
            capability_type="action",
            capability_rid=action_type_rid,
            status="running",
            params=params,
            safety_level="unknown",
            side_effects=[],
            user_id=user_id,
            branch=branch,
        )
        await session.commit()

        # Schedule background execution
        asyncio.create_task(
            self._execute_async_background(
                execution_id, action_type_rid, params,
                tenant_id=tenant_id, user_id=user_id,
                branch=branch, skip_confirmation=skip_confirmation,
            )
        )

        return ExecutionResponse(
            execution_id=execution_id,
            status="running",
            started_at=datetime.now(tz=UTC),
        )

    async def _execute_async_background(
        self,
        execution_id: str,
        action_type_rid: str,
        params: dict[str, Any],
        *,
        tenant_id: str,
        user_id: str,
        branch: str | None = None,
        skip_confirmation: bool = False,
    ) -> None:
        """Background execution task."""
        from lingshu.infra.database import get_session as _get_session

        try:
            async for session in _get_session():
                # Execute the action
                result = await self.execute_action(
                    action_type_rid, params, session,
                    branch=branch, skip_confirmation=True,
                )

                # Update the original execution record
                repo = ExecutionRepository(session)
                await repo.update_status(
                    execution_id, tenant_id,
                    status="success",
                    result=result.result,
                    completed_at=datetime.now(tz=UTC),
                )
                await session.commit()
        except Exception as e:
            try:
                async for session in _get_session():
                    repo = ExecutionRepository(session)
                    await repo.update_status(
                        execution_id, tenant_id,
                        status="failed",
                        result={"error": str(e)},
                        completed_at=datetime.now(tz=UTC),
                    )
                    await session.commit()
            except Exception:
                logger.exception(
                    "Failed to update execution %s status to failed",
                    execution_id,
                )

    # ── Confirm / Cancel ─────────────────────────────────────────

    async def confirm_execution(
        self, execution_id: str, session: AsyncSession,
    ) -> ExecutionResponse:
        """Confirm a pending execution."""
        tenant_id = get_tenant_id()
        repo = ExecutionRepository(session)
        execution = await repo.get_by_id(execution_id, tenant_id)

        if not execution:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Execution {execution_id} not found",
            )

        if execution.status != "pending_confirmation":
            raise AppError(
                code=ErrorCode.COMMON_INVALID_INPUT,
                message=f"Execution {execution_id} is not pending confirmation",
            )

        # Check expiry
        if execution.started_at:
            expiry = execution.started_at + CONFIRMATION_TTL
            if datetime.now(tz=UTC) > expiry:
                await self._audit.log_complete(
                    session,
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    status="expired",
                )
                await session.commit()
                raise AppError(
                    code=ErrorCode.FUNCTION_CONFIRMATION_EXPIRED,
                    message="Confirmation window has expired",
                )

        # Re-execute with skip_confirmation
        result = await self.execute_action(
            execution.capability_rid,
            execution.params,
            session,
            branch=execution.branch,
            skip_confirmation=True,
        )

        # Update original execution
        await repo.update_status(
            execution_id, tenant_id,
            status="success",
            result={"delegated_to": result.execution_id},
            completed_at=datetime.now(tz=UTC),
            confirmed_at=datetime.now(tz=UTC),
            confirmed_by="user",
        )
        await session.commit()
        return result

    async def cancel_execution(
        self, execution_id: str, session: AsyncSession,
    ) -> ExecutionResponse:
        """Cancel a pending execution."""
        tenant_id = get_tenant_id()
        repo = ExecutionRepository(session)
        execution = await repo.get_by_id(execution_id, tenant_id)

        if not execution:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Execution {execution_id} not found",
            )

        if execution.status != "pending_confirmation":
            raise AppError(
                code=ErrorCode.COMMON_INVALID_INPUT,
                message=f"Execution {execution_id} is not pending confirmation",
            )

        await self._audit.log_complete(
            session,
            execution_id=execution_id,
            tenant_id=tenant_id,
            status="cancelled",
        )
        await session.commit()

        return ExecutionResponse(
            execution_id=execution_id,
            status="cancelled",
            completed_at=datetime.now(tz=UTC),
        )

    # ── Execution Queries ────────────────────────────────────────

    async def get_execution(
        self, execution_id: str, session: AsyncSession,
    ) -> ExecutionDetailResponse:
        tenant_id = get_tenant_id()
        repo = ExecutionRepository(session)
        execution = await repo.get_by_id(execution_id, tenant_id)
        if not execution:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"Execution {execution_id} not found",
            )
        return self._execution_to_response(execution)

    async def query_executions(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
        capability_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[ExecutionDetailResponse], int]:
        tenant_id = get_tenant_id()
        repo = ExecutionRepository(session)
        executions, total = await repo.list_by_tenant(
            tenant_id,
            offset=offset,
            limit=limit,
            capability_type=capability_type,
            status=status,
        )
        return [self._execution_to_response(e) for e in executions], total

    # ── Global Function Management ───────────────────────────────

    async def create_function(
        self,
        api_name: str,
        display_name: str,
        description: str | None,
        parameters: list[dict[str, Any]],
        implementation: dict[str, Any],
        session: AsyncSession,
    ) -> GlobalFunctionResponse:
        return await self._registry.register(
            session,
            api_name=api_name,
            display_name=display_name,
            description=description,
            parameters=parameters,
            implementation=implementation,
        )

    async def get_function(
        self, rid: str, session: AsyncSession,
    ) -> GlobalFunctionResponse:
        return await self._registry.get(rid, session)

    async def update_function(
        self, rid: str, updates: dict[str, Any], session: AsyncSession,
    ) -> GlobalFunctionResponse:
        return await self._registry.update(rid, updates, session)

    async def delete_function(
        self, rid: str, session: AsyncSession,
    ) -> None:
        return await self._registry.delete(rid, session)

    async def query_functions(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[GlobalFunctionResponse], int]:
        return await self._registry.query(session, offset=offset, limit=limit)

    async def execute_function(
        self,
        rid: str,
        params: dict[str, Any],
        session: AsyncSession,
        *,
        branch: str | None = None,
    ) -> ExecutionResponse:
        """Execute a global function."""
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"

        # Get function definition
        func_response = await self._registry.get(rid, session)

        # Log start
        await self._audit.log_start(
            session,
            execution_id=execution_id,
            tenant_id=tenant_id,
            capability_type="function",
            capability_rid=rid,
            status="running",
            params=params,
            safety_level="SAFETY_READ_ONLY",
            side_effects=[],
            user_id=user_id,
            branch=branch,
        )

        try:
            result = await self._executor.execute(
                func_response.implementation, params, tenant_id,
            )
            result_data = {"data": result}
            await self._audit.log_complete(
                session,
                execution_id=execution_id,
                tenant_id=tenant_id,
                status="success",
                result=result_data,
            )
            await session.commit()

            return ExecutionResponse(
                execution_id=execution_id,
                status="success",
                result=result_data,
                started_at=datetime.now(tz=UTC),
                completed_at=datetime.now(tz=UTC),
            )
        except AppError:
            await self._audit.log_complete(
                session,
                execution_id=execution_id,
                tenant_id=tenant_id,
                status="failed",
            )
            await session.commit()
            raise

    # ── Capability Catalog ───────────────────────────────────────

    async def list_capabilities(
        self,
        session: AsyncSession,
        *,
        capability_type: str | None = None,
    ) -> list[CapabilityDescriptor]:
        """Aggregate capabilities from actions and functions."""
        tenant_id = get_tenant_id()
        results: list[CapabilityDescriptor] = []

        # Functions
        if capability_type is None or capability_type == "function":
            repo = GlobalFunctionRepository(session)
            funcs, _ = await repo.list_by_tenant(
                tenant_id, is_active=True, limit=1000,
            )
            for f in funcs:
                results.append(CapabilityDescriptor(
                    type="function",
                    rid=f.rid,
                    api_name=f.api_name,
                    display_name=f.display_name,
                    description=f.description,
                    parameters=f.parameters,
                    outputs=[],
                    safety_level="SAFETY_READ_ONLY",
                    side_effects=[],
                ))

        # Actions from ontology
        if capability_type is None or capability_type == "action":
            try:
                action_nodes, _ = await self._ontology.query_action_types(
                    tenant_id, limit=1000,
                )
                for node in action_nodes:
                    exec_config = node.get("execution", {})
                    if isinstance(exec_config, str):
                        import json
                        try:
                            exec_config = json.loads(exec_config)
                        except (json.JSONDecodeError, TypeError):
                            exec_config = {}
                    params_raw = node.get("parameters", [])
                    if isinstance(params_raw, str):
                        import json
                        try:
                            params_raw = json.loads(params_raw)
                        except (json.JSONDecodeError, TypeError):
                            params_raw = []
                    results.append(CapabilityDescriptor(
                        type="action",
                        rid=node.get("rid", ""),
                        api_name=node.get("api_name", ""),
                        display_name=node.get("display_name", ""),
                        description=node.get("description"),
                        parameters=params_raw if isinstance(params_raw, list) else [],
                        outputs=[],
                        safety_level=node.get("safety_level", "SAFETY_READ_ONLY"),
                        side_effects=[],
                    ))
            except Exception:
                logger.warning("Failed to query action types for capabilities", exc_info=True)

        # Workflows
        if capability_type is None or capability_type == "workflow":
            try:
                wf_repo = WorkflowRepository(session)
                workflows, _ = await wf_repo.list_by_tenant(
                    tenant_id, is_active=True, limit=1000,
                )
                for wf in workflows:
                    results.append(CapabilityDescriptor(
                        type="workflow",
                        rid=wf.rid,
                        api_name=wf.api_name,
                        display_name=wf.display_name,
                        description=wf.description,
                        parameters=wf.parameters if isinstance(wf.parameters, list) else [],
                        outputs=[],
                        safety_level=wf.safety_level or "SAFETY_READ_ONLY",
                        side_effects=wf.side_effects if isinstance(wf.side_effects, list) else [],
                    ))
            except Exception:
                logger.warning("Failed to query workflows for capabilities", exc_info=True)

        return results

    # ── Overview ─────────────────────────────────────────────────

    async def get_overview(
        self, session: AsyncSession,
    ) -> FunctionOverviewResponse:
        tenant_id = get_tenant_id()

        func_repo = GlobalFunctionRepository(session)
        func_count = await func_repo.count_by_tenant(tenant_id)

        exec_repo = ExecutionRepository(session)
        since = datetime.now(tz=UTC) - timedelta(hours=24)
        by_status = await exec_repo.count_recent(tenant_id, since)
        total_24h = sum(by_status.values())

        # Action count from ontology
        action_count = 0
        try:
            _, action_count = await self._ontology.query_action_types(
                tenant_id, limit=1,
            )
        except Exception:
            logger.warning("Failed to query action type count", exc_info=True)

        # Workflow count
        wf_repo = WorkflowRepository(session)
        workflow_count = await wf_repo.count_by_tenant(tenant_id)

        return FunctionOverviewResponse(
            capabilities={
                "actions": action_count,
                "functions": func_count,
                "workflows": workflow_count,
            },
            recent_executions={
                "total_24h": total_24h,
                "by_status": by_status,
            },
        )

    # ── Helpers ───────────────────────────────────────────────────

    def _execution_to_response(
        self, execution: Any,
    ) -> ExecutionDetailResponse:
        return ExecutionDetailResponse(
            execution_id=execution.execution_id,
            capability_type=execution.capability_type,
            capability_rid=execution.capability_rid,
            status=execution.status,
            params=execution.params,
            result=execution.result,
            safety_level=execution.safety_level,
            side_effects=execution.side_effects,
            user_id=execution.user_id,
            branch=execution.branch,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            confirmed_at=execution.confirmed_at,
            confirmed_by=execution.confirmed_by,
        )
