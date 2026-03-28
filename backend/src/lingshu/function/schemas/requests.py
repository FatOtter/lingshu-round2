"""Function module request DTOs."""

from typing import Any

from pydantic import BaseModel, Field

from lingshu.infra.models import QueryRequest


class ExecuteActionRequest(BaseModel):
    """Request to execute an action."""

    params: dict[str, Any] = Field(default_factory=dict)
    branch: str | None = None
    skip_confirmation: bool = False


class ValidateActionRequest(BaseModel):
    """Request to validate action parameters without executing."""

    params: dict[str, Any] = Field(default_factory=dict)


class QueryActionsRequest(QueryRequest):
    """Query available actions."""

    pass


class CreateGlobalFunctionRequest(BaseModel):
    """Request to register a new global function."""

    api_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    implementation: dict[str, Any] = Field(default_factory=dict)


class UpdateGlobalFunctionRequest(BaseModel):
    """Request to update a global function."""

    display_name: str | None = None
    description: str | None = None
    parameters: list[dict[str, Any]] | None = None
    implementation: dict[str, Any] | None = None


class ExecuteGlobalFunctionRequest(BaseModel):
    """Request to execute a global function."""

    params: dict[str, Any] = Field(default_factory=dict)
    branch: str | None = None


class QueryExecutionsRequest(QueryRequest):
    """Query execution history."""

    capability_type: str | None = None
    status: str | None = None


class ExecuteActionBatchRequest(BaseModel):
    """Request to execute an action in batch."""

    batch_params: list[dict[str, Any]]
    branch: str | None = None
    skip_confirmation: bool = False


class QueryCapabilitiesRequest(QueryRequest):
    """Query unified capability catalog."""

    capability_type: str | None = None


# ── Workflow Requests ────────────────────────────────────────────


class WorkflowNodeRequest(BaseModel):
    """Node definition in a create/update workflow request."""

    node_id: str
    type: str = Field(description="action | global_function | condition | wait")
    capability_rid: str | None = None
    input_mappings: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    label: str | None = None


class WorkflowEdgeRequest(BaseModel):
    """Edge definition in a create/update workflow request."""

    source_node_id: str
    target_node_id: str
    condition: str | None = None


class CreateWorkflowRequest(BaseModel):
    """Request to create a new workflow."""

    api_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    nodes: list[WorkflowNodeRequest] = Field(default_factory=list)
    edges: list[WorkflowEdgeRequest] = Field(default_factory=list)
    status: str = Field(default="draft")


class UpdateWorkflowRequest(BaseModel):
    """Request to update an existing workflow."""

    display_name: str | None = None
    description: str | None = None
    nodes: list[WorkflowNodeRequest] | None = None
    edges: list[WorkflowEdgeRequest] | None = None
    status: str | None = None


class QueryWorkflowsRequest(QueryRequest):
    """Query workflows."""

    status: str | None = None


class ExecuteWorkflowRequest(BaseModel):
    """Request to execute a workflow."""

    inputs: dict[str, Any] = Field(default_factory=dict)
    branch: str | None = None
