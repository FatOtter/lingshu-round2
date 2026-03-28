"""Common DTOs: Filter, SortSpec, Pagination, PagedResponse, ApiResponse."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FilterOperator(StrEnum):
    """Supported filter operators."""

    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    IN = "in"


class SortOrder(StrEnum):
    """Sort direction."""

    ASC = "asc"
    DESC = "desc"


class Filter(BaseModel):
    """A single filter condition."""

    field: str
    operator: FilterOperator
    value: Any


class SortSpec(BaseModel):
    """A single sort specification."""

    field: str
    order: SortOrder = SortOrder.ASC


class PaginationRequest(BaseModel):
    """Pagination parameters for list queries."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class QueryRequest(BaseModel):
    """Standard list query request body."""

    filters: list[Filter] = Field(default_factory=list)
    sort: list[SortSpec] = Field(default_factory=list)
    pagination: PaginationRequest = Field(default_factory=PaginationRequest)


class PaginationResponse(BaseModel):
    """Pagination metadata in list responses."""

    total: int
    page: int
    page_size: int
    has_next: bool


class Metadata(BaseModel):
    """Response metadata."""

    request_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ApiResponse[T](BaseModel):
    """Standard API success response."""

    data: T
    metadata: Metadata = Field(default_factory=Metadata)


class PagedResponse[T](BaseModel):
    """Standard paginated list response."""

    data: list[T]
    pagination: PaginationResponse
    metadata: Metadata = Field(default_factory=Metadata)


class ErrorDetail(BaseModel):
    """Error detail in error responses."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard API error response."""

    error: ErrorDetail
    metadata: Metadata = Field(default_factory=Metadata)
