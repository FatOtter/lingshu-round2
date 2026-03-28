"""Request DTOs for Ontology module APIs."""

from typing import Any

from pydantic import BaseModel, Field

from lingshu.infra.models import PaginationRequest


class CreateEntityRequest(BaseModel):
    """Base request for creating any Ontology entity."""

    api_name: str
    display_name: str
    description: str | None = None
    lifecycle_status: str = "ACTIVE"


class CreateObjectTypeRequest(CreateEntityRequest):
    implements_interface_type_rids: list[str] = Field(default_factory=list)
    primary_key_property_type_rids: list[str] = Field(default_factory=list)
    validation: dict[str, Any] | None = None
    asset_mapping: dict[str, Any] | None = None


class CreateLinkTypeRequest(CreateEntityRequest):
    source_object_type_rid: str | None = None
    source_interface_type_rid: str | None = None
    target_object_type_rid: str | None = None
    target_interface_type_rid: str | None = None
    cardinality: str = "ONE_TO_MANY"
    implements_interface_type_rids: list[str] = Field(default_factory=list)
    primary_key_property_type_rids: list[str] = Field(default_factory=list)
    validation: dict[str, Any] | None = None
    asset_mapping: dict[str, Any] | None = None


class CreateInterfaceTypeRequest(CreateEntityRequest):
    category: str  # OBJECT_INTERFACE | LINK_INTERFACE
    extends_interface_type_rids: list[str] = Field(default_factory=list)
    required_shared_property_type_rids: list[str] = Field(default_factory=list)
    link_requirements: list[dict[str, Any]] = Field(default_factory=list)
    object_constraint: dict[str, Any] | None = None


class CreateSharedPropertyTypeRequest(CreateEntityRequest):
    data_type: str  # DT_STRING, DT_INTEGER, etc.
    widget: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None


class CreateActionTypeRequest(CreateEntityRequest):
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    execution: dict[str, Any] | None = None
    safety_level: str = "SAFETY_READ_ONLY"
    side_effects: list[dict[str, Any]] = Field(default_factory=list)


class UpdateEntityRequest(BaseModel):
    """Base request for updating any Ontology entity."""

    display_name: str | None = None
    description: str | None = None
    lifecycle_status: str | None = None


class UpdateObjectTypeRequest(UpdateEntityRequest):
    implements_interface_type_rids: list[str] | None = None
    primary_key_property_type_rids: list[str] | None = None
    validation: dict[str, Any] | None = None
    asset_mapping: dict[str, Any] | None = None


class UpdateLinkTypeRequest(UpdateEntityRequest):
    cardinality: str | None = None
    implements_interface_type_rids: list[str] | None = None
    primary_key_property_type_rids: list[str] | None = None
    validation: dict[str, Any] | None = None
    asset_mapping: dict[str, Any] | None = None


class UpdateInterfaceTypeRequest(UpdateEntityRequest):
    extends_interface_type_rids: list[str] | None = None
    required_shared_property_type_rids: list[str] | None = None
    link_requirements: list[dict[str, Any]] | None = None
    object_constraint: dict[str, Any] | None = None


class UpdateSharedPropertyTypeRequest(UpdateEntityRequest):
    widget: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None


class UpdateActionTypeRequest(UpdateEntityRequest):
    parameters: list[dict[str, Any]] | None = None
    execution: dict[str, Any] | None = None
    safety_level: str | None = None
    side_effects: list[dict[str, Any]] | None = None


class CreatePropertyTypeRequest(BaseModel):
    """Create a PropertyType attached to an ObjectType or LinkType."""

    api_name: str
    display_name: str
    description: str | None = None
    data_type: str
    inherit_from_shared_property_type_rid: str | None = None
    physical_column: str | None = None
    virtual_expression: str | None = None
    widget: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None


class UpdatePropertyTypeRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    physical_column: str | None = None
    virtual_expression: str | None = None
    widget: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None


class QueryEntitiesRequest(BaseModel):
    search: str | None = None
    lifecycle_status: str | None = None
    include_drafts: bool = True
    pagination: PaginationRequest = Field(default_factory=PaginationRequest)


class CommitStagingRequest(BaseModel):
    commit_message: str | None = None


class DiscardStagingRequest(BaseModel):
    rids: list[str] = Field(default_factory=list)  # Empty = discard all


class SearchRequest(BaseModel):
    q: str
    types: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
