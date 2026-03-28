"""SettingServiceImpl: business logic for auth, users, tenants, members, audit logs."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.config import Settings
from lingshu.infra.context import get_request_id, get_role, get_tenant_id, get_user_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.rid import generate_rid
from lingshu.setting.auth.jit_provisioning import JitProvisioner
from lingshu.setting.auth.oidc_provider import OidcConfig, OidcProvider
from lingshu.setting.auth.password import (
    hash_password,
    validate_password_strength,
    verify_password,
)
from lingshu.setting.auth.provider import BuiltinProvider
from lingshu.setting.authz.enforcer import PermissionEnforcer
from lingshu.setting.schemas.responses import SsoConfigResponse
from lingshu.setting.models import (
    AuditLog,
    CustomRole,
    RefreshToken,
    Tenant,
    User,
    UserTenantMembership,
)
from lingshu.setting.repository.audit_log_repo import AuditLogRepository
from lingshu.setting.repository.membership_repo import MembershipRepository
from lingshu.setting.repository.refresh_token_repo import RefreshTokenRepository
from lingshu.setting.repository.role_repo import CustomRoleRepository
from lingshu.setting.repository.tenant_repo import TenantRepository
from lingshu.setting.repository.user_repo import UserRepository
from lingshu.setting.schemas.requests import (
    AddMemberRequest,
    ChangePasswordRequest,
    CreateRoleRequest,
    CreateTenantRequest,
    CreateUserRequest,
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
    TenantBrief,
    TenantResponse,
    UserResponse,
)


class SettingServiceImpl:
    """Implementation of SettingService protocol + router-facing business logic."""

    def __init__(
        self,
        provider: BuiltinProvider,
        enforcer: PermissionEnforcer,
        settings: Settings | None = None,
        refresh_ttl: int = 604800,
    ) -> None:
        self._provider = provider
        self._enforcer = enforcer
        self._refresh_ttl = refresh_ttl
        self._settings = settings

        # SSO support — initialised only when OIDC is configured
        self._oidc_provider: OidcProvider | None = None
        self._jit_provisioner: JitProvisioner | None = None
        if settings is not None and settings.sso_enabled:
            oidc_config = OidcConfig(
                issuer_url=settings.oidc_issuer_url,
                client_id=settings.oidc_client_id,
                client_secret=settings.oidc_client_secret,
                redirect_uri=settings.oidc_redirect_uri,
            )
            self._oidc_provider = OidcProvider(oidc_config)
            self._jit_provisioner = JitProvisioner()

    # ── Protocol interface methods ────────────────────────────────

    def get_current_user_id(self) -> str:
        return get_user_id()

    def get_current_tenant_id(self) -> str:
        return get_tenant_id()

    def check_permission(
        self,
        user_id: str,
        resource_type: str,
        action: str,
        resource_rid: str | None = None,
    ) -> bool:
        return self._enforcer.check_permission(user_id, resource_type, action, resource_rid)

    async def write_audit_log(
        self,
        module: str,
        event_type: str,
        action: str,
        resource_type: str | None = None,
        resource_rid: str | None = None,
        details: dict[str, Any] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        if session is None:
            return  # Can't write without a session
        repo = AuditLogRepository(session)
        log = AuditLog(
            tenant_id=get_tenant_id(),
            module=module,
            event_type=event_type,
            resource_type=resource_type,
            resource_rid=resource_rid,
            user_id=get_user_id(),
            action=action,
            details=details,
            request_id=get_request_id(),
        )
        await repo.create(log)

    # ── Auth operations ────────────────────────────────────────────

    async def login(
        self, email: str, password: str, session: AsyncSession
    ) -> tuple[LoginResponse, str, str]:
        """Authenticate user. Returns (response, access_token, refresh_raw_token)."""
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)
        refresh_repo = RefreshTokenRepository(session)

        user = await user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AppError(
                code=ErrorCode.SETTING_AUTH_INVALID_CREDENTIALS,
                message="Invalid email or password",
            )

        if user.status == "disabled":
            raise AppError(
                code=ErrorCode.SETTING_PERMISSION_DENIED,
                message="User account is disabled",
            )

        # Find default tenant
        default_membership = await membership_repo.get_default_tenant(user.rid)
        if default_membership is None:
            memberships = await membership_repo.list_by_user(user.rid)
            if not memberships:
                raise AppError(
                    code=ErrorCode.COMMON_INTERNAL_ERROR,
                    message="User has no tenant membership",
                )
            default_membership = memberships[0]

        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_by_rid(default_membership.tenant_rid)
        if tenant is None:
            raise AppError(
                code=ErrorCode.COMMON_INTERNAL_ERROR,
                message="Tenant not found",
            )

        # Sync user role to enforcer
        self._enforcer.sync_user_role(user.rid, default_membership.role)

        # Issue tokens
        access_token = self._provider.issue_access_token(
            user.rid, tenant.rid, default_membership.role
        )
        refresh_raw, refresh_hash = self._provider.issue_refresh_token(user.rid, tenant.rid)

        await refresh_repo.create(
            RefreshToken(
                token_hash=refresh_hash,
                user_rid=user.rid,
                tenant_rid=tenant.rid,
                expires_at=datetime.now(UTC) + timedelta(seconds=self._refresh_ttl),
            )
        )

        response = LoginResponse(
            user=UserResponse(
                rid=user.rid,
                email=user.email,
                display_name=user.display_name,
                status=user.status,
                role=default_membership.role,
                tenant=TenantBrief(rid=tenant.rid, display_name=tenant.display_name),
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )
        return response, access_token, refresh_raw

    async def logout(self, access_token: str, refresh_raw: str | None, session: AsyncSession) -> None:
        """Revoke current tokens."""
        try:
            payload = self._provider.validate_token(access_token)
            await self._provider.revoke_token(payload.jti, payload.exp)
        except ValueError:
            pass  # Token already expired, just continue

        if refresh_raw:
            refresh_hash = hashlib.sha256(refresh_raw.encode()).hexdigest()
            refresh_repo = RefreshTokenRepository(session)
            await refresh_repo.revoke(refresh_hash)

    async def refresh(
        self, refresh_raw: str, session: AsyncSession
    ) -> tuple[str, str]:
        """Refresh access token. Returns (new_access_token, new_refresh_raw)."""
        refresh_hash = hashlib.sha256(refresh_raw.encode()).hexdigest()
        refresh_repo = RefreshTokenRepository(session)
        membership_repo = MembershipRepository(session)

        token = await refresh_repo.get_by_hash(refresh_hash)
        if token is None or not refresh_repo.is_valid(token):
            raise AppError(
                code=ErrorCode.SETTING_AUTH_TOKEN_EXPIRED,
                message="Refresh token is invalid or expired",
            )

        # Revoke old refresh token
        await refresh_repo.revoke(refresh_hash)

        # Get current role
        membership = await membership_repo.get(token.user_rid, token.tenant_rid)
        role = membership.role if membership else "member"

        # Issue new tokens
        access_token = self._provider.issue_access_token(token.user_rid, token.tenant_rid, role)
        new_refresh_raw, new_refresh_hash = self._provider.issue_refresh_token(
            token.user_rid, token.tenant_rid
        )
        await refresh_repo.create(
            RefreshToken(
                token_hash=new_refresh_hash,
                user_rid=token.user_rid,
                tenant_rid=token.tenant_rid,
                expires_at=datetime.now(UTC) + timedelta(seconds=self._refresh_ttl),
            )
        )
        return access_token, new_refresh_raw

    async def get_me(self, session: AsyncSession) -> UserResponse:
        """Get current authenticated user info."""
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)
        tenant_repo = TenantRepository(session)

        user_id = get_user_id()
        tenant_id = get_tenant_id()

        user = await user_repo.get_by_rid(user_id)
        if user is None:
            raise AppError(code=ErrorCode.SETTING_USER_NOT_FOUND, message="User not found")

        membership = await membership_repo.get(user_id, tenant_id)
        tenant = await tenant_repo.get_by_rid(tenant_id)

        return UserResponse(
            rid=user.rid,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            role=membership.role if membership else None,
            tenant=TenantBrief(rid=tenant.rid, display_name=tenant.display_name)
            if tenant
            else None,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def change_password(
        self, req: ChangePasswordRequest, session: AsyncSession
    ) -> None:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_rid(get_user_id())
        if user is None:
            raise AppError(code=ErrorCode.SETTING_USER_NOT_FOUND, message="User not found")

        if not verify_password(req.current_password, user.password_hash):
            raise AppError(
                code=ErrorCode.SETTING_AUTH_INVALID_CREDENTIALS,
                message="Current password is incorrect",
            )

        error = validate_password_strength(req.new_password)
        if error:
            raise AppError(code=ErrorCode.COMMON_INVALID_INPUT, message=error)

        await user_repo.update_fields(user.rid, password_hash=hash_password(req.new_password))

    # ── User CRUD ──────────────────────────────────────────────────

    async def create_user(
        self, req: CreateUserRequest, session: AsyncSession
    ) -> UserResponse:
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)

        existing = await user_repo.get_by_email(req.email)
        if existing is not None:
            raise AppError(
                code=ErrorCode.SETTING_USER_EMAIL_EXISTS,
                message=f"Email {req.email} is already registered",
            )

        error = validate_password_strength(req.password)
        if error:
            raise AppError(code=ErrorCode.COMMON_INVALID_INPUT, message=error)

        user_rid = generate_rid("user")
        tenant_rid = get_tenant_id()

        user = await user_repo.create(
            User(
                rid=user_rid,
                email=req.email,
                display_name=req.display_name,
                password_hash=hash_password(req.password),
            )
        )

        await membership_repo.create(
            UserTenantMembership(
                user_rid=user_rid,
                tenant_rid=tenant_rid,
                role=req.role,
                is_default=True,
            )
        )

        # Sync the new user's role to the enforcer
        self._enforcer.sync_user_role(user_rid, req.role)

        return UserResponse(
            rid=user.rid,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            role=req.role,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def get_user(self, rid: str, session: AsyncSession) -> UserResponse:
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)

        user = await user_repo.get_by_rid(rid)
        if user is None:
            raise AppError(code=ErrorCode.SETTING_USER_NOT_FOUND, message="User not found")

        tenant_rid = get_tenant_id()
        membership = await membership_repo.get(rid, tenant_rid)

        return UserResponse(
            rid=user.rid,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            role=membership.role if membership else None,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def update_user(
        self, rid: str, req: UpdateUserRequest, session: AsyncSession
    ) -> UserResponse:
        user_repo = UserRepository(session)
        fields = req.model_dump(exclude_none=True)
        if not fields:
            raise AppError(code=ErrorCode.COMMON_INVALID_INPUT, message="No fields to update")

        user = await user_repo.update_fields(rid, **fields)
        if user is None:
            raise AppError(code=ErrorCode.SETTING_USER_NOT_FOUND, message="User not found")

        return UserResponse(
            rid=user.rid,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def delete_user(self, rid: str, session: AsyncSession) -> None:
        """Soft delete: set status to disabled."""
        user_repo = UserRepository(session)
        user = await user_repo.update_fields(rid, status="disabled")
        if user is None:
            raise AppError(code=ErrorCode.SETTING_USER_NOT_FOUND, message="User not found")

    async def reset_password(
        self, rid: str, req: ResetPasswordRequest, session: AsyncSession
    ) -> None:
        user_repo = UserRepository(session)
        error = validate_password_strength(req.new_password)
        if error:
            raise AppError(code=ErrorCode.COMMON_INVALID_INPUT, message=error)

        user = await user_repo.update_fields(rid, password_hash=hash_password(req.new_password))
        if user is None:
            raise AppError(code=ErrorCode.SETTING_USER_NOT_FOUND, message="User not found")

    async def query_users(
        self, session: AsyncSession, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[UserResponse], int]:
        user_repo = UserRepository(session)
        tenant_rid = get_tenant_id()
        users, total = await user_repo.list_by_tenant(tenant_rid, offset=offset, limit=limit)
        membership_repo = MembershipRepository(session)

        results = []
        for user in users:
            m = await membership_repo.get(user.rid, tenant_rid)
            results.append(
                UserResponse(
                    rid=user.rid,
                    email=user.email,
                    display_name=user.display_name,
                    status=user.status,
                    role=m.role if m else None,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
            )
        return results, total

    # ── Tenant CRUD ────────────────────────────────────────────────

    async def create_tenant(
        self, req: CreateTenantRequest, session: AsyncSession
    ) -> TenantResponse:
        """Create a new tenant and add the creator as admin member."""
        tenant_repo = TenantRepository(session)
        membership_repo = MembershipRepository(session)

        tenant_rid = generate_rid("tenant")
        creator_rid = get_user_id()

        tenant = await tenant_repo.create(
            Tenant(
                rid=tenant_rid,
                display_name=req.display_name,
                config=req.config or {},
            )
        )

        await membership_repo.create(
            UserTenantMembership(
                user_rid=creator_rid,
                tenant_rid=tenant_rid,
                role="admin",
                is_default=False,
            )
        )

        return TenantResponse(
            rid=tenant.rid,
            display_name=tenant.display_name,
            status=tenant.status,
            config=tenant.config,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )

    async def get_tenant(
        self, rid: str, session: AsyncSession
    ) -> TenantResponse:
        """Get a single tenant by RID."""
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_by_rid(rid)
        if tenant is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Tenant not found")

        return TenantResponse(
            rid=tenant.rid,
            display_name=tenant.display_name,
            status=tenant.status,
            config=tenant.config,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )

    async def update_tenant(
        self, rid: str, req: UpdateTenantRequest, session: AsyncSession
    ) -> TenantResponse:
        """Update tenant fields."""
        tenant_repo = TenantRepository(session)
        fields = req.model_dump(exclude_none=True)
        if not fields:
            raise AppError(code=ErrorCode.COMMON_INVALID_INPUT, message="No fields to update")

        tenant = await tenant_repo.update_fields(rid, **fields)
        if tenant is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Tenant not found")

        return TenantResponse(
            rid=tenant.rid,
            display_name=tenant.display_name,
            status=tenant.status,
            config=tenant.config,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )

    async def delete_tenant(self, rid: str, session: AsyncSession) -> None:
        """Soft delete: set tenant status to disabled."""
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.update_fields(rid, status="disabled")
        if tenant is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Tenant not found")

    async def query_tenants(
        self, session: AsyncSession, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[TenantResponse], int]:
        """List tenants. Admin sees all; member/viewer sees only their tenants."""
        tenant_repo = TenantRepository(session)
        current_role = get_role()
        current_user = get_user_id()

        if current_role == "admin":
            tenants, total = await tenant_repo.list_all(offset=offset, limit=limit)
        else:
            tenants, total = await tenant_repo.list_by_user(
                current_user, offset=offset, limit=limit
            )

        return [
            TenantResponse(
                rid=t.rid,
                display_name=t.display_name,
                status=t.status,
                config=t.config,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tenants
        ], total

    async def switch_tenant(
        self, req: SwitchTenantRequest, session: AsyncSession
    ) -> tuple[str, str, str]:
        """Switch to a different tenant.

        Returns (access_token, refresh_raw, role) for the new tenant context.
        """
        membership_repo = MembershipRepository(session)
        tenant_repo = TenantRepository(session)
        refresh_repo = RefreshTokenRepository(session)

        user_rid = get_user_id()

        # Validate membership
        membership = await membership_repo.get(user_rid, req.tenant_rid)
        if membership is None:
            raise AppError(
                code=ErrorCode.SETTING_PERMISSION_DENIED,
                message="You are not a member of this tenant",
            )

        # Validate tenant exists and is active
        tenant = await tenant_repo.get_by_rid(req.tenant_rid)
        if tenant is None or tenant.status != "active":
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message="Tenant not found or disabled",
            )

        # Sync user role for the new tenant context
        self._enforcer.sync_user_role(user_rid, membership.role)

        # Issue new tokens for the switched tenant
        access_token = self._provider.issue_access_token(
            user_rid, tenant.rid, membership.role
        )
        refresh_raw, refresh_hash = self._provider.issue_refresh_token(
            user_rid, tenant.rid
        )
        await refresh_repo.create(
            RefreshToken(
                token_hash=refresh_hash,
                user_rid=user_rid,
                tenant_rid=tenant.rid,
                expires_at=datetime.now(UTC) + timedelta(seconds=self._refresh_ttl),
            )
        )

        return access_token, refresh_raw, membership.role

    # ── Member Management ──────────────────────────────────────────

    async def add_member(
        self, tenant_rid: str, req: AddMemberRequest, session: AsyncSession
    ) -> MemberResponse:
        """Add a user to a tenant."""
        membership_repo = MembershipRepository(session)
        user_repo = UserRepository(session)
        tenant_repo = TenantRepository(session)

        # Validate tenant exists
        tenant = await tenant_repo.get_by_rid(tenant_rid)
        if tenant is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Tenant not found")

        # Validate user exists
        user = await user_repo.get_by_rid(req.user_rid)
        if user is None:
            raise AppError(code=ErrorCode.SETTING_USER_NOT_FOUND, message="User not found")

        # Check if already a member
        existing = await membership_repo.get(req.user_rid, tenant_rid)
        if existing is not None:
            raise AppError(
                code=ErrorCode.COMMON_CONFLICT,
                message="User is already a member of this tenant",
            )

        membership = await membership_repo.create(
            UserTenantMembership(
                user_rid=req.user_rid,
                tenant_rid=tenant_rid,
                role=req.role,
                is_default=False,
            )
        )

        # Sync role to enforcer
        self._enforcer.sync_user_role(req.user_rid, req.role)

        return MemberResponse(
            user_rid=user.rid,
            display_name=user.display_name,
            email=user.email,
            role=membership.role,
            is_default=membership.is_default,
            created_at=membership.created_at,
        )

    async def update_member_role(
        self,
        tenant_rid: str,
        user_rid: str,
        req: UpdateMemberRoleRequest,
        session: AsyncSession,
    ) -> MemberResponse:
        """Update a member's role in a tenant."""
        membership_repo = MembershipRepository(session)
        user_repo = UserRepository(session)

        membership = await membership_repo.get(user_rid, tenant_rid)
        if membership is None:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message="Membership not found",
            )

        old_role = membership.role

        # Update role in DB
        updated = await membership_repo.update_role(user_rid, tenant_rid, req.role)
        if updated is None:
            raise AppError(
                code=ErrorCode.COMMON_INTERNAL_ERROR,
                message="Failed to update membership role",
            )

        # Update enforcer: remove old role, add new
        self._enforcer.remove_user_role(user_rid, old_role)
        self._enforcer.sync_user_role(user_rid, req.role)

        user = await user_repo.get_by_rid(user_rid)
        if user is None:
            raise AppError(code=ErrorCode.SETTING_USER_NOT_FOUND, message="User not found")

        return MemberResponse(
            user_rid=user.rid,
            display_name=user.display_name,
            email=user.email,
            role=updated.role,
            is_default=updated.is_default,
            created_at=updated.created_at,
        )

    async def remove_member(
        self, tenant_rid: str, user_rid: str, session: AsyncSession
    ) -> None:
        """Remove a user from a tenant."""
        membership_repo = MembershipRepository(session)

        membership = await membership_repo.get(user_rid, tenant_rid)
        if membership is None:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message="Membership not found",
            )

        # Prevent removing the last admin
        if membership.role == "admin":
            members, _ = await membership_repo.list_by_tenant(tenant_rid)
            admin_count = sum(1 for m in members if m.role == "admin")
            if admin_count <= 1:
                raise AppError(
                    code=ErrorCode.COMMON_INVALID_INPUT,
                    message="Cannot remove the last admin from a tenant",
                )

        # Remove enforcer role
        self._enforcer.remove_user_role(user_rid, membership.role)

        await membership_repo.delete(user_rid, tenant_rid)

    async def query_members(
        self,
        tenant_rid: str,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[MemberResponse], int]:
        """List members of a tenant with pagination."""
        membership_repo = MembershipRepository(session)
        user_repo = UserRepository(session)
        tenant_repo = TenantRepository(session)

        # Validate tenant exists
        tenant = await tenant_repo.get_by_rid(tenant_rid)
        if tenant is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Tenant not found")

        memberships, total = await membership_repo.list_by_tenant(
            tenant_rid, offset=offset, limit=limit
        )

        results: list[MemberResponse] = []
        for m in memberships:
            user = await user_repo.get_by_rid(m.user_rid)
            if user is not None:
                results.append(
                    MemberResponse(
                        user_rid=user.rid,
                        display_name=user.display_name,
                        email=user.email,
                        role=m.role,
                        is_default=m.is_default,
                        created_at=m.created_at,
                    )
                )
        return results, total

    # ── Custom Role CRUD ──────────────────────────────────────────

    async def create_role(
        self, req: CreateRoleRequest, session: AsyncSession
    ) -> RoleResponse:
        """Create a custom role and sync permissions to Casbin."""
        repo = CustomRoleRepository(session)
        tenant_id = get_tenant_id()

        # Check for name collision
        existing = await repo.get_by_name(tenant_id, req.name)
        if existing is not None:
            raise AppError(
                code=ErrorCode.COMMON_CONFLICT,
                message=f"Role with name '{req.name}' already exists in this tenant",
            )

        role_rid = generate_rid("role")
        permissions_data = [p.model_dump(exclude_none=True) for p in req.permissions]

        role = await repo.create(
            CustomRole(
                rid=role_rid,
                tenant_id=tenant_id,
                name=req.name,
                description=req.description,
                permissions=permissions_data,
                is_system=False,
            )
        )

        # Sync to Casbin
        self._enforcer.add_custom_role_policies(req.name, permissions_data)

        return self._role_to_response(role)

    async def get_role(
        self, rid: str, session: AsyncSession
    ) -> RoleResponse:
        """Get a single custom role by RID."""
        repo = CustomRoleRepository(session)
        role = await repo.get_by_rid(rid)
        if role is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Role not found")
        return self._role_to_response(role)

    async def update_role(
        self, rid: str, req: UpdateRoleRequest, session: AsyncSession
    ) -> RoleResponse:
        """Update a custom role. System roles cannot be modified."""
        repo = CustomRoleRepository(session)

        role = await repo.get_by_rid(rid)
        if role is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Role not found")
        if role.is_system:
            raise AppError(
                code=ErrorCode.SETTING_PERMISSION_DENIED,
                message="System roles cannot be modified",
            )

        fields: dict[str, Any] = {}
        if req.name is not None:
            # Check for name collision with other roles
            tenant_id = get_tenant_id()
            existing = await repo.get_by_name(tenant_id, req.name)
            if existing is not None and existing.rid != rid:
                raise AppError(
                    code=ErrorCode.COMMON_CONFLICT,
                    message=f"Role with name '{req.name}' already exists in this tenant",
                )
            fields["name"] = req.name
        if req.description is not None:
            fields["description"] = req.description
        if req.permissions is not None:
            permissions_data = [p.model_dump(exclude_none=True) for p in req.permissions]
            fields["permissions"] = permissions_data

        if not fields:
            raise AppError(code=ErrorCode.COMMON_INVALID_INPUT, message="No fields to update")

        old_name = role.name
        updated = await repo.update_fields(rid, **fields)
        if updated is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Role not found")

        # Re-sync Casbin policies: remove old, add new
        self._enforcer.remove_role_policies(old_name)
        new_name = updated.name
        self._enforcer.add_custom_role_policies(new_name, updated.permissions)

        return self._role_to_response(updated)

    async def delete_role(
        self, rid: str, session: AsyncSession
    ) -> None:
        """Delete a custom role. System roles cannot be deleted."""
        repo = CustomRoleRepository(session)

        role = await repo.get_by_rid(rid)
        if role is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Role not found")
        if role.is_system:
            raise AppError(
                code=ErrorCode.SETTING_PERMISSION_DENIED,
                message="System roles cannot be deleted",
            )

        # Remove from Casbin
        self._enforcer.remove_role_policies(role.name)

        await repo.delete(rid)

    async def query_roles(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[RoleResponse], int]:
        """List all roles (system + custom) for the current tenant."""
        repo = CustomRoleRepository(session)
        tenant_id = get_tenant_id()
        roles, total = await repo.list_by_tenant(tenant_id, offset=offset, limit=limit)
        return [self._role_to_response(r) for r in roles], total

    async def assign_role_to_user(
        self, user_rid: str, role_name: str, session: AsyncSession
    ) -> None:
        """Update a user's role in membership and Casbin for the current tenant."""
        membership_repo = MembershipRepository(session)
        tenant_rid = get_tenant_id()

        membership = await membership_repo.get(user_rid, tenant_rid)
        if membership is None:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message="Membership not found",
            )

        old_role = membership.role
        await membership_repo.update_role(user_rid, tenant_rid, role_name)

        # Update enforcer
        self._enforcer.remove_user_role(user_rid, old_role)
        self._enforcer.sync_user_role(user_rid, role_name)

    # ── Audit logs ─────────────────────────────────────────────────

    async def cleanup_audit_logs(
        self, session: AsyncSession, *, days: int = 90,
    ) -> int:
        """Delete audit logs older than specified days. Returns deleted count."""
        repo = AuditLogRepository(session)
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        count = await repo.delete_before(get_tenant_id(), cutoff)
        return count

    async def query_audit_logs(
        self,
        session: AsyncSession,
        *,
        module: str | None = None,
        event_type: str | None = None,
        user_id: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AuditLogResponse], int]:
        repo = AuditLogRepository(session)
        logs, total = await repo.query(
            get_tenant_id(),
            module=module,
            event_type=event_type,
            user_id=user_id,
            offset=offset,
            limit=limit,
        )
        return [self._log_to_response(log) for log in logs], total

    async def get_audit_log(
        self, log_id: int, session: AsyncSession
    ) -> AuditLogResponse:
        repo = AuditLogRepository(session)
        log = await repo.get_by_id(log_id, get_tenant_id())
        if log is None:
            raise AppError(code=ErrorCode.COMMON_NOT_FOUND, message="Audit log not found")
        return self._log_to_response(log)

    # ── Overview ───────────────────────────────────────────────────

    async def get_overview(self, session: AsyncSession) -> OverviewResponse:
        tenant_rid = get_tenant_id()
        user_repo = UserRepository(session)
        tenant_repo = TenantRepository(session)
        audit_repo = AuditLogRepository(session)

        by_status = await user_repo.count_by_status(tenant_rid)
        total_users = sum(by_status.values())
        total_tenants = await tenant_repo.count()
        recent = await audit_repo.recent(tenant_rid)

        return OverviewResponse(
            users={"total": total_users, "by_status": by_status},
            tenants={"total": total_tenants},
            recent_audit=[self._log_to_response(log) for log in recent],
        )

    # ── SSO operations ──────────────────────────────────────────────

    async def sso_authorize(self) -> tuple[str, str]:
        """Generate SSO authorization URL. Returns (authorization_url, state)."""
        if self._oidc_provider is None:
            raise AppError(
                code=ErrorCode.COMMON_INVALID_INPUT,
                message="SSO is not configured",
            )
        state = OidcProvider.generate_state()
        nonce = OidcProvider.generate_nonce()
        url = await self._oidc_provider.get_authorization_url(state, nonce)
        return url, state

    async def sso_callback(
        self, code: str, state: str, session: AsyncSession
    ) -> tuple[LoginResponse, str, str]:
        """Complete SSO login: exchange code, provision user, issue tokens.

        Returns (login_response, access_token, refresh_raw).
        """
        if self._oidc_provider is None or self._jit_provisioner is None:
            raise AppError(
                code=ErrorCode.COMMON_INVALID_INPUT,
                message="SSO is not configured",
            )

        # Exchange authorization code for IdP tokens
        token_response = await self._oidc_provider.exchange_code(code, state)
        idp_access_token = token_response.get("access_token", "")

        # Fetch user info from IdP
        userinfo = await self._oidc_provider.get_userinfo(idp_access_token)
        if not userinfo.email:
            raise AppError(
                code=ErrorCode.SETTING_AUTH_INVALID_CREDENTIALS,
                message="OIDC provider did not return an email address",
            )

        # Determine default tenant
        tenant_repo = TenantRepository(session)
        membership_repo = MembershipRepository(session)
        refresh_repo = RefreshTokenRepository(session)

        # JIT provision (create or update) the local user
        # Use the first available tenant as default for new users
        tenants, _ = await tenant_repo.list_all(offset=0, limit=1)
        if not tenants:
            raise AppError(
                code=ErrorCode.COMMON_INTERNAL_ERROR,
                message="No tenant available for SSO provisioning",
            )
        default_tenant = tenants[0]

        user = await self._jit_provisioner.provision_user(
            userinfo, default_tenant.rid, session
        )

        if user.status == "disabled":
            raise AppError(
                code=ErrorCode.SETTING_PERMISSION_DENIED,
                message="User account is disabled",
            )

        # Find membership for token issuance
        default_membership = await membership_repo.get_default_tenant(user.rid)
        if default_membership is None:
            memberships = await membership_repo.list_by_user(user.rid)
            if not memberships:
                raise AppError(
                    code=ErrorCode.COMMON_INTERNAL_ERROR,
                    message="User has no tenant membership after provisioning",
                )
            default_membership = memberships[0]

        tenant = await tenant_repo.get_by_rid(default_membership.tenant_rid)
        if tenant is None:
            raise AppError(
                code=ErrorCode.COMMON_INTERNAL_ERROR,
                message="Tenant not found",
            )

        # Sync role and issue tokens (same as login flow)
        self._enforcer.sync_user_role(user.rid, default_membership.role)

        access_token = self._provider.issue_access_token(
            user.rid, tenant.rid, default_membership.role
        )
        refresh_raw, refresh_hash = self._provider.issue_refresh_token(
            user.rid, tenant.rid
        )
        await refresh_repo.create(
            RefreshToken(
                token_hash=refresh_hash,
                user_rid=user.rid,
                tenant_rid=tenant.rid,
                expires_at=datetime.now(UTC) + timedelta(seconds=self._refresh_ttl),
            )
        )

        response = LoginResponse(
            user=UserResponse(
                rid=user.rid,
                email=user.email,
                display_name=user.display_name,
                status=user.status,
                role=default_membership.role,
                tenant=TenantBrief(rid=tenant.rid, display_name=tenant.display_name),
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )
        return response, access_token, refresh_raw

    def get_sso_config(self) -> SsoConfigResponse:
        """Return public SSO configuration."""
        if self._settings is None or not self._settings.sso_enabled:
            return SsoConfigResponse(enabled=False)
        return SsoConfigResponse(
            enabled=True,
            provider_name=self._settings.oidc_provider_name,
        )

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _role_to_response(role: CustomRole) -> RoleResponse:
        return RoleResponse(
            rid=role.rid,
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            is_system=role.is_system,
            created_at=role.created_at,
            updated_at=role.updated_at,
        )

    @staticmethod
    def _log_to_response(log: AuditLog) -> AuditLogResponse:
        return AuditLogResponse(
            log_id=log.log_id,
            module=log.module,
            event_type=log.event_type,
            resource_type=log.resource_type,
            resource_rid=log.resource_rid,
            user_id=log.user_id,
            action=log.action,
            details=log.details,
            request_id=log.request_id,
            created_at=log.created_at,
        )
