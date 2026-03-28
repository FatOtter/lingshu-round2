"""Response DTOs for Ontology module APIs."""

from typing import Any

from pydantic import BaseModel, Field


class EntityResponse(BaseModel):
    """Base response for any Ontology entity."""

    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    lifecycle_status: str = "ACTIVE"
    version_status: str | None = None  # "active", "draft", "staging"
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class ObjectTypeResponse(EntityResponse):
    implements_interface_type_rids: list[str] = Field(default_factory=list)
    primary_key_property_type_rids: list[str] = Field(default_factory=list)
    property_types: list["PropertyTypeResponse"] = Field(default_factory=list)
    validation: dict[str, Any] | None = None
    asset_mapping: dict[str, Any] | None = None


class LinkTypeResponse(EntityResponse):
    source_object_type_rid: str | None = None
    source_interface_type_rid: str | None = None
    target_object_type_rid: str | None = None
    target_interface_type_rid: str | None = None
    cardinality: str = "ONE_TO_MANY"
    implements_interface_type_rids: list[str] = Field(default_factory=list)
    primary_key_property_type_rids: list[str] = Field(default_factory=list)
    property_types: list["PropertyTypeResponse"] = Field(default_factory=list)
    validation: dict[str, Any] | None = None
    asset_mapping: dict[str, Any] | None = None


class InterfaceTypeResponse(EntityResponse):
    category: str = "OBJECT_INTERFACE"
    extends_interface_type_rids: list[str] = Field(default_factory=list)
    required_shared_property_type_rids: list[str] = Field(default_factory=list)
    link_requirements: list[dict[str, Any]] = Field(default_factory=list)
    object_constraint: dict[str, Any] | None = None


class SharedPropertyTypeResponse(EntityResponse):
    data_type: str = "DT_STRING"
    widget: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None


class ActionTypeResponse(EntityResponse):
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    execution: dict[str, Any] | None = None
    safety_level: str = "SAFETY_READ_ONLY"
    side_effects: list[dict[str, Any]] = Field(default_factory=list)


class PropertyTypeResponse(BaseModel):
    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    data_type: str = "DT_STRING"
    inherit_from_shared_property_type_rid: str | None = None
    physical_column: str | None = None
    virtual_expression: str | None = None
    widget: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None


class TopologyResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class StagingSummaryResponse(BaseModel):
    counts: dict[str, int]
    total: int = 0


class DraftsSummaryResponse(BaseModel):
    counts: dict[str, int]
    total: int = 0


class SnapshotResponse(BaseModel):
    snapshot_id: str
    parent_snapshot_id: str | None = None
    tenant_id: str
    commit_message: str | None = None
    author: str
    entity_changes: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class SnapshotDiffResponse(BaseModel):
    snapshot_changes: dict[str, Any] = Field(default_factory=dict)
    current_changes: dict[str, Any] = Field(default_factory=dict)


class SearchResultResponse(BaseModel):
    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    entity_type: str


class LockStatusResponse(BaseModel):
    rid: str
    locked: bool
    locked_by: str | None = None
    expires_in: int | None = None  # seconds
