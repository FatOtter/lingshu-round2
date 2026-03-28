"""Request DTOs for Data module APIs."""

from typing import Any

from pydantic import BaseModel, Field

from lingshu.infra.models import Filter, PaginationRequest, SortSpec


class CreateConnectionRequest(BaseModel):
    display_name: str
    type: str  # "postgresql" | "iceberg"
    config: dict[str, Any]
    credentials: str | None = None


class UpdateConnectionRequest(BaseModel):
    display_name: str | None = None
    config: dict[str, Any] | None = None
    credentials: str | None = None


class QueryConnectionsRequest(BaseModel):
    type: str | None = None
    pagination: PaginationRequest = Field(default_factory=PaginationRequest)


class QueryInstancesRequest(BaseModel):
    filters: list[Filter] = Field(default_factory=list)
    sort: list[SortSpec] = Field(default_factory=list)
    pagination: PaginationRequest = Field(default_factory=PaginationRequest)


class GetInstanceRequest(BaseModel):
    primary_key: dict[str, Any]


class CreateBranchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    from_ref: str = Field(default="main")


class MergeBranchRequest(BaseModel):
    target: str = Field(default="main")
