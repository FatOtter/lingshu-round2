"""Setting module API routes: auth, users, tenants, members, audit logs, overview."""

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.infra.database import get_session
from lingshu.infra.models import ApiResponse, Metadata, PagedResponse, PaginationResponse
from lingshu.setting.schemas.requests import (
    AddMemberRequest,
    ChangePasswordRequest,
    CleanupAuditLogsRequest,
    CreateRoleRequest,
    CreateTenantRequest,
    CreateUserRequest,
    QueryAuditLogRequest,
    QueryRolesRequest,
    QueryTenantsRequest,
    QueryUsersRequest,
    ResetPasswordRequest,
    SwitchTenantRequest,
    UpdateMemberRoleRequest,
    UpdateRoleRequest,
    UpdateTenantRequest,
    UpdateUserRequest,
)
from lingshu.setting.schemas.responses import (
    AuditLogResponse,
    LoginResponse,
    MemberResponse,
    OverviewResponse,
    RoleResponse,
    SsoConfigResponse,
    TenantResponse,
    UserResponse,
)
from lingshu.setting.service import SettingServiceImpl

router = APIRouter(prefix="/setting/v1", tags=["setting"])

# Service is injected via app.state in main.py
_service: SettingServiceImpl | None = None


def set_service(service: SettingServiceImpl) -> None:
    global _service
    _service = service


def get_service() -> SettingServiceImpl:
    if _service is None:
        raise RuntimeError("SettingService not initialized")
    return _service


async def get_db() -> AsyncGenerator[AsyncSession]:
    async for session in get_session():
        yield session


# ── Auth API ─────────────────────────────────────────────────────

class LoginRequest:
    """Workaround to avoid shadowing the schema import."""
    pass


@router.post("/auth/login")
async def login(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[LoginResponse]:
    from lingshu.setting.schemas.requests import LoginRequest as LoginReq

    body = await request.json()
    req = LoginReq(**body)
    svc = get_service()
    login_resp, access_token, refresh_raw = await svc.login(req.email, req.password, session)

    _is_secure = not svc._provider._settings.is_dev
    response.set_cookie(
        key="lingshu_access",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=_is_secure,
        max_age=svc._provider._access_ttl,
        path="/",
    )
    response.set_cookie(
        key="lingshu_refresh",
        value=refresh_raw,
        httponly=True,
        samesite="lax",
        secure=_is_secure,
        max_age=svc._refresh_ttl,
        path="/setting/v1/auth/refresh",
    )

    return ApiResponse(data=login_resp)


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    access_token = request.cookies.get("lingshu_access", "")
    refresh_raw = request.cookies.get("lingshu_refresh")
    await svc.logout(access_token, refresh_raw, session)

    response.delete_cookie("lingshu_access", path="/")
    response.delete_cookie("lingshu_refresh", path="/setting/v1/auth/refresh")

    return ApiResponse(data={"message": "Logged out"})


@router.post("/auth/refresh")
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    refresh_raw = request.cookies.get("lingshu_refresh")
    if not refresh_raw:
        from lingshu.infra.errors import AppError, ErrorCode

        raise AppError(
            code=ErrorCode.SETTING_AUTH_TOKEN_EXPIRED,
            message="No refresh token",
        )

    access_token, new_refresh_raw = await svc.refresh(refresh_raw, session)

    response.set_cookie(
        key="lingshu_access",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=svc._provider._access_ttl,
        path="/",
    )
    response.set_cookie(
        key="lingshu_refresh",
        value=new_refresh_raw,
        httponly=True,
        samesite="lax",
        max_age=svc._refresh_ttl,
        path="/setting/v1/auth/refresh",
    )

    return ApiResponse(data={"message": "Token refreshed"})


@router.get("/auth/me")
async def me(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[UserResponse]:
    svc = get_service()
    user = await svc.get_me(session)
    return ApiResponse(data=user)


@router.post("/auth/change-password")
async def change_password(
    req: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    await svc.change_password(req, session)
    return ApiResponse(data={"message": "Password changed"})


# ── SSO API ──────────────────────────────────────────────────────


@router.get("/auth/sso/config")
async def sso_config() -> ApiResponse[SsoConfigResponse]:
    svc = get_service()
    config = svc.get_sso_config()
    return ApiResponse(data=config)


@router.get("/auth/sso/authorize")
async def sso_authorize() -> RedirectResponse:
    svc = get_service()
    url, _state = await svc.sso_authorize()
    return RedirectResponse(url=url, status_code=302)


@router.post("/auth/sso/callback")
async def sso_callback(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[LoginResponse]:
    from lingshu.setting.schemas.requests import SsoCallbackRequest

    body = await request.json()
    req = SsoCallbackRequest(**body)
    svc = get_service()
    login_resp, access_token, refresh_raw = await svc.sso_callback(
        req.code, req.state, session
    )

    _is_secure = not svc._provider._settings.is_dev
    response.set_cookie(
        key="lingshu_access",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=_is_secure,
        max_age=svc._provider._access_ttl,
        path="/",
    )
    response.set_cookie(
        key="lingshu_refresh",
        value=refresh_raw,
        httponly=True,
        samesite="lax",
        secure=_is_secure,
        max_age=svc._refresh_ttl,
        path="/setting/v1/auth/refresh",
    )

    return ApiResponse(data=login_resp)


# ── User API ─────────────────────────────────────────────────────

@router.post("/users", status_code=201)
async def create_user(
    req: CreateUserRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[UserResponse]:
    svc = get_service()
    user = await svc.create_user(req, session)
    return ApiResponse(data=user)


@router.post("/users/query")
async def query_users(
    req: QueryUsersRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[UserResponse]:
    svc = get_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    users, total = await svc.query_users(session, offset=offset, limit=req.pagination.page_size)
    return PagedResponse(
        data=users,
        pagination=PaginationResponse(
            total=total,
            page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/users/{rid}")
async def get_user(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[UserResponse]:
    svc = get_service()
    user = await svc.get_user(rid, session)
    return ApiResponse(data=user)


@router.put("/users/{rid}")
async def update_user(
    rid: str,
    req: UpdateUserRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[UserResponse]:
    svc = get_service()
    user = await svc.update_user(rid, req, session)
    return ApiResponse(data=user)


@router.delete("/users/{rid}")
async def delete_user(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    await svc.delete_user(rid, session)
    return ApiResponse(data={"message": "User disabled"})


@router.post("/users/{rid}/reset-password")
async def reset_password(
    rid: str,
    req: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    await svc.reset_password(rid, req, session)
    return ApiResponse(data={"message": "Password reset"})


# ── Tenant API ──────────────────────────────────────────────────

@router.post("/tenants", status_code=201)
async def create_tenant(
    req: CreateTenantRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TenantResponse]:
    svc = get_service()
    tenant = await svc.create_tenant(req, session)
    return ApiResponse(data=tenant)


@router.post("/tenants/query")
async def query_tenants(
    req: QueryTenantsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[TenantResponse]:
    svc = get_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    tenants, total = await svc.query_tenants(
        session, offset=offset, limit=req.pagination.page_size
    )
    return PagedResponse(
        data=tenants,
        pagination=PaginationResponse(
            total=total,
            page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/tenants/{rid}")
async def get_tenant(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TenantResponse]:
    svc = get_service()
    tenant = await svc.get_tenant(rid, session)
    return ApiResponse(data=tenant)


@router.put("/tenants/{rid}")
async def update_tenant(
    rid: str,
    req: UpdateTenantRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TenantResponse]:
    svc = get_service()
    tenant = await svc.update_tenant(rid, req, session)
    return ApiResponse(data=tenant)


@router.delete("/tenants/{rid}")
async def delete_tenant(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    await svc.delete_tenant(rid, session)
    return ApiResponse(data={"message": "Tenant disabled"})


@router.post("/tenants/switch")
async def switch_tenant(
    req: SwitchTenantRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    access_token, refresh_raw, role = await svc.switch_tenant(req, session)

    _is_secure = not svc._provider._settings.is_dev
    response.set_cookie(
        key="lingshu_access",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=_is_secure,
        max_age=svc._provider._access_ttl,
        path="/",
    )
    response.set_cookie(
        key="lingshu_refresh",
        value=refresh_raw,
        httponly=True,
        samesite="lax",
        secure=_is_secure,
        max_age=svc._refresh_ttl,
        path="/setting/v1/auth/refresh",
    )

    return ApiResponse(
        data={
            "message": "Tenant switched",
            "tenant_rid": req.tenant_rid,
            "role": role,
        }
    )


# ── Member API ──────────────────────────────────────────────────

@router.post("/tenants/{rid}/members", status_code=201)
async def add_member(
    rid: str,
    req: AddMemberRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[MemberResponse]:
    svc = get_service()
    member = await svc.add_member(rid, req, session)
    return ApiResponse(data=member)


@router.post("/tenants/{rid}/members/query")
async def query_members(
    rid: str,
    req: QueryTenantsRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[MemberResponse]:
    svc = get_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    members, total = await svc.query_members(
        rid, session, offset=offset, limit=req.pagination.page_size
    )
    return PagedResponse(
        data=members,
        pagination=PaginationResponse(
            total=total,
            page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.put("/tenants/{rid}/members/{user_rid}")
async def update_member_role(
    rid: str,
    user_rid: str,
    req: UpdateMemberRoleRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[MemberResponse]:
    svc = get_service()
    member = await svc.update_member_role(rid, user_rid, req, session)
    return ApiResponse(data=member)


@router.delete("/tenants/{rid}/members/{user_rid}")
async def remove_member(
    rid: str,
    user_rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    await svc.remove_member(rid, user_rid, session)
    return ApiResponse(data={"message": "Member removed"})


# ── Role API ─────────────────────────────────────────────────────

@router.post("/roles", status_code=201)
async def create_role(
    req: CreateRoleRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[RoleResponse]:
    svc = get_service()
    role = await svc.create_role(req, session)
    return ApiResponse(data=role)


@router.post("/roles/query")
async def query_roles(
    req: QueryRolesRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[RoleResponse]:
    svc = get_service()
    offset = (req.pagination.page - 1) * req.pagination.page_size
    roles, total = await svc.query_roles(
        session, offset=offset, limit=req.pagination.page_size
    )
    return PagedResponse(
        data=roles,
        pagination=PaginationResponse(
            total=total,
            page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/roles/{rid}")
async def get_role(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[RoleResponse]:
    svc = get_service()
    role = await svc.get_role(rid, session)
    return ApiResponse(data=role)


@router.put("/roles/{rid}")
async def update_role(
    rid: str,
    req: UpdateRoleRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[RoleResponse]:
    svc = get_service()
    role = await svc.update_role(rid, req, session)
    return ApiResponse(data=role)


@router.delete("/roles/{rid}")
async def delete_role(
    rid: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    await svc.delete_role(rid, session)
    return ApiResponse(data={"message": "Role deleted"})


# ── Audit API ────────────────────────────────────────────────────

@router.post("/audit-logs/query")
async def query_audit_logs(
    req: QueryAuditLogRequest,
    session: AsyncSession = Depends(get_db),
) -> PagedResponse[AuditLogResponse]:
    svc = get_service()
    # Extract filter values
    filters = {f.field: f.value for f in req.filters}
    offset = (req.pagination.page - 1) * req.pagination.page_size
    logs, total = await svc.query_audit_logs(
        session,
        module=filters.get("module"),
        event_type=filters.get("event_type"),
        user_id=filters.get("user_id"),
        offset=offset,
        limit=req.pagination.page_size,
    )
    return PagedResponse(
        data=logs,
        pagination=PaginationResponse(
            total=total,
            page=req.pagination.page,
            page_size=req.pagination.page_size,
            has_next=(offset + req.pagination.page_size) < total,
        ),
        metadata=Metadata(),
    )


@router.get("/audit-logs/{log_id}")
async def get_audit_log(
    log_id: int,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[AuditLogResponse]:
    svc = get_service()
    log = await svc.get_audit_log(log_id, session)
    return ApiResponse(data=log)


@router.post("/audit-logs/cleanup")
async def cleanup_audit_logs(
    req: CleanupAuditLogsRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    svc = get_service()
    deleted = await svc.cleanup_audit_logs(session, days=req.days)
    return ApiResponse(data={"deleted_count": deleted})


# ── Overview API ─────────────────────────────────────────────────

@router.get("/overview")
async def overview(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[OverviewResponse]:
    svc = get_service()
    data = await svc.get_overview(session)
    return ApiResponse(data=data)
