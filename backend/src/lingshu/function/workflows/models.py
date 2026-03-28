"""Workflow definition ORM model — extends the existing Workflow stub in function/models.py.

The existing Workflow model in function/models.py stores basic metadata.
This module provides Pydantic schemas for the JSONB `definition` column
which contains the full DAG structure (nodes + edges).
"""

from typing import Any

from pydantic import BaseModel, Field


class WorkflowNodeSchema(BaseModel):
    """A single node in the workflow DAG."""

    node_id: str
    type: str = Field(
        description="Node type: action | global_function | condition | wait"
    )
    capability_rid: str | None = None
    input_mappings: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(
        default_factory=lambda: {"x": 0, "y": 0}
    )
    label: str | None = None


class WorkflowEdgeSchema(BaseModel):
    """A directed edge in the workflow DAG."""

    source_node_id: str
    target_node_id: str
    condition: str | None = None


class WorkflowDefinition(BaseModel):
    """Full workflow DAG stored in Workflow.definition JSONB column."""

    nodes: list[WorkflowNodeSchema] = Field(default_factory=list)
    edges: list[WorkflowEdgeSchema] = Field(default_factory=list)
