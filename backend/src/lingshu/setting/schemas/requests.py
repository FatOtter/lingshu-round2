"""Request DTOs for Setting module APIs."""

from typing import Any

from pydantic import BaseModel, EmailStr, Field

from lingshu.infra.models import QueryRequest


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    role: str = Field(default="member", pattern="^(admin|member|viewer)$")


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class QueryUsersRequest(QueryRequest):
    pass


class QueryAuditLogRequest(QueryRequest):
    pass


# ── Tenant requests ────────────────────────────────────────────


class CreateTenantRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    config: dict[str, Any] | None = None


class UpdateTenantRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = Field(default=None, pattern="^(active|disabled)$")
    config: dict[str, Any] | None = None


class SwitchTenantRequest(BaseModel):
    tenant_rid: str


class QueryTenantsRequest(QueryRequest):
    pass


# ── Member requests ────────────────────────────────────────────


class AddMemberRequest(BaseModel):
    user_rid: str
    role: str = Field(default="member", pattern="^(admin|member|viewer)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|member|viewer)$")


# ── Role requests ─────────────────────────────────────────────


class PermissionEntry(BaseModel):
    resource_type: str
    action: str
    resource_rid: str | None = None


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    permissions: list[PermissionEntry]


class UpdateRoleRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    permissions: list[PermissionEntry] | None = None


class QueryRolesRequest(QueryRequest):
    pass


class CleanupAuditLogsRequest(BaseModel):
    days: int = Field(default=90, ge=1, le=3650)


# ── SSO requests ──────────────────────────────────────────────


class SsoCallbackRequest(BaseModel):
    code: str
    state: str
