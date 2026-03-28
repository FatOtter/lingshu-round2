"""Response DTOs for Setting module APIs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TenantBrief(BaseModel):
    rid: str
    display_name: str


class UserResponse(BaseModel):
    rid: str
    email: str
    display_name: str
    status: str
    role: str | None = None
    tenant: TenantBrief | None = None
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    user: UserResponse


class TenantResponse(BaseModel):
    rid: str
    display_name: str
    status: str
    config: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class MemberResponse(BaseModel):
    user_rid: str
    display_name: str
    email: str
    role: str
    is_default: bool
    created_at: datetime


class AuditLogResponse(BaseModel):
    log_id: int
    module: str
    event_type: str
    resource_type: str | None = None
    resource_rid: str | None = None
    user_id: str
    action: str
    details: dict[str, Any] | None = None
    request_id: str | None = None
    created_at: datetime


class RoleResponse(BaseModel):
    rid: str
    name: str
    description: str | None = None
    permissions: list[dict[str, Any]]
    is_system: bool
    created_at: datetime
    updated_at: datetime


class OverviewResponse(BaseModel):
    users: dict[str, Any]
    tenants: dict[str, Any]
    recent_audit: list[AuditLogResponse]


class SsoConfigResponse(BaseModel):
    enabled: bool
    provider_name: str | None = None
    authorization_url: str | None = None
