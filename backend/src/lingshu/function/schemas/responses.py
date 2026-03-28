"""Function module response DTOs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionResponse(BaseModel):
    """Execution result or pending confirmation response."""

    execution_id: str
    status: str
    result: dict[str, Any] | None = None
    confirmation: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionDetailResponse(BaseModel):
    """Full execution record."""

    execution_id: str
    capability_type: str
    capability_rid: str
    status: str
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    safety_level: str | None = None
    side_effects: list[dict[str, Any]] = Field(default_factory=list)
    user_id: str
    branch: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None


class GlobalFunctionResponse(BaseModel):
    """Global function details."""

    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    implementation: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CapabilityDescriptor(BaseModel):
    """Unified capability descriptor for catalog."""

    type: str
    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    safety_level: str = "SAFETY_READ_ONLY"
    side_effects: list[dict[str, Any]] = Field(default_factory=list)


class ValidationResponse(BaseModel):
    """Parameter validation result."""

    valid: bool
    errors: list[dict[str, Any]] = Field(default_factory=list)


class FunctionOverviewResponse(BaseModel):
    """Function module overview."""

    capabilities: dict[str, int] = Field(default_factory=dict)
    recent_executions: dict[str, Any] = Field(default_factory=dict)


# ── Workflow Responses ────────────────────────────────────────────


class WorkflowNodeResponse(BaseModel):
    """Node in workflow response."""

    node_id: str
    type: str
    capability_rid: str | None = None
    input_mappings: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    label: str | None = None


class WorkflowEdgeResponse(BaseModel):
    """Edge in workflow response."""

    source_node_id: str
    target_node_id: str
    condition: str | None = None


class WorkflowResponse(BaseModel):
    """Workflow details."""

    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    nodes: list[WorkflowNodeResponse] = Field(default_factory=list)
    edges: list[WorkflowEdgeResponse] = Field(default_factory=list)
    safety_level: str = "SAFETY_READ_ONLY"
    status: str = "draft"
    version: int = 1
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowExecutionResponse(BaseModel):
    """Workflow execution result."""

    execution_id: str
    workflow_rid: str
    status: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
