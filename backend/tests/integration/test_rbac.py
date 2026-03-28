"""Integration tests for RBAC permission flows across service + enforcer layers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.setting.auth.provider import BuiltinProvider
from lingshu.config import Settings
from lingshu.setting.authz.enforcer import PermissionEnforcer
from lingshu.setting.models import CustomRole, Tenant, User, UserTenantMembership
from lingshu.setting.schemas.requests import (
    CreateRoleRequest,
    PermissionEntry,
    UpdateRoleRequest,
)
from lingshu.setting.service import SettingServiceImpl


# ── Helpers ───────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _build_service() -> SettingServiceImpl:
    provider = MagicMock(spec=BuiltinProvider)
    provider.issue_access_token.return_value = "access_tok"
    provider.issue_refresh_token.return_value = ("refresh_raw", "refresh_hash")
    provider._access_ttl = 900

    enforcer = PermissionEnforcer(settings=Settings(rbac_enabled=True))
    enforcer.seed_policies()
    return SettingServiceImpl(provider=provider, enforcer=enforcer)


def _mock_session() -> AsyncMock:
    return AsyncMock()


# ── Tests ─────────────────────────────────────────────────────────


class TestAdminAccessAll:
    """Admin can access everything."""

    def test_admin_full_access(self) -> None:
        service = _build_service()
        service._enforcer.sync_user_role("ri.user.admin", "admin")

        assert service.check_permission("ri.user.admin", "tenant", "write") is True
        assert service.check_permission("ri.user.admin", "user", "delete") is True
        assert service.check_permission("ri.user.admin", "object_type", "read") is True
        assert service.check_permission("ri.user.admin", "action", "execute") is True
        assert service.check_permission("ri.user.admin", "connection", "create") is True


class TestMemberReadNotDelete:
    """Member can read but not delete users/tenants."""

    def test_member_permissions(self) -> None:
        service = _build_service()
        service._enforcer.sync_user_role("ri.user.member", "member")

        # Can read anything
        assert service.check_permission("ri.user.member", "object_type", "read") is True
        assert service.check_permission("ri.user.member", "tenant", "read") is True

        # Can write business entities
        assert service.check_permission("ri.user.member", "object_type", "create") is True
        assert service.check_permission("ri.user.member", "connection", "write") is True
        assert service.check_permission("ri.user.member", "action", "execute") is True

        # Cannot manage users or tenants
        assert service.check_permission("ri.user.member", "user", "create") is False
        assert service.check_permission("ri.user.member", "tenant", "write") is False


class TestViewerReadOnly:
    """Viewer can only read."""

    def test_viewer_permissions(self) -> None:
        service = _build_service()
        service._enforcer.sync_user_role("ri.user.viewer", "viewer")

        # Can read
        assert service.check_permission("ri.user.viewer", "object_type", "read") is True
        assert service.check_permission("ri.user.viewer", "tenant", "read") is True

        # Cannot write or execute
        assert service.check_permission("ri.user.viewer", "object_type", "create") is False
        assert service.check_permission("ri.user.viewer", "action", "execute") is False
        assert service.check_permission("ri.user.viewer", "connection", "write") is False
        assert service.check_permission("ri.user.viewer", "user", "delete") is False


class TestCustomRolePermissions:
    """Custom role with specific permissions."""

    async def test_create_custom_role_and_check(self) -> None:
        service = _build_service()
        session = _mock_session()

        custom_role = CustomRole(
            rid="ri.role.custom1",
            tenant_id="t1",
            name="data_editor",
            description="Can edit data entities only",
            permissions=[
                {"resource_type": "object_type", "action": "read"},
                {"resource_type": "object_type", "action": "write"},
                {"resource_type": "connection", "action": "read"},
            ],
            is_system=False,
        )
        custom_role.created_at = _now()
        custom_role.updated_at = _now()

        with (
            patch("lingshu.setting.service.get_tenant_id", return_value="t1"),
            patch("lingshu.setting.service.generate_rid", return_value="ri.role.custom1"),
            patch("lingshu.setting.service.CustomRoleRepository") as MockRoleRepo,
        ):
            MockRoleRepo.return_value.get_by_name = AsyncMock(return_value=None)
            MockRoleRepo.return_value.create = AsyncMock(return_value=custom_role)

            req = CreateRoleRequest(
                name="data_editor",
                description="Can edit data entities only",
                permissions=[
                    PermissionEntry(resource_type="object_type", action="read"),
                    PermissionEntry(resource_type="object_type", action="write"),
                    PermissionEntry(resource_type="connection", action="read"),
                ],
            )
            result = await service.create_role(req, session)
            assert result.name == "data_editor"

        # Assign user to custom role
        service._enforcer.sync_user_role("ri.user.editor", "data_editor")

        # Check permissions
        assert service.check_permission("ri.user.editor", "object_type", "read") is True
        assert service.check_permission("ri.user.editor", "object_type", "write") is True
        assert service.check_permission("ri.user.editor", "connection", "read") is True
        # Should not have access to other things
        assert service.check_permission("ri.user.editor", "user", "write") is False
        assert service.check_permission("ri.user.editor", "action", "execute") is False


class TestResourceLevelPermission:
    """Resource-level permission check."""

    def test_resource_specific_permission(self) -> None:
        service = _build_service()

        # Add a specific resource-level policy
        service._enforcer._enforcer.add_policy("analyst", "object_type", "read", "ri.obj.42")
        service._enforcer.sync_user_role("ri.user.analyst", "analyst")

        # Can read specific resource
        assert service.check_permission(
            "ri.user.analyst", "object_type", "read", "ri.obj.42",
        ) is True
        # Cannot read other resources
        assert service.check_permission(
            "ri.user.analyst", "object_type", "read", "ri.obj.99",
        ) is False
        # Cannot write
        assert service.check_permission(
            "ri.user.analyst", "object_type", "write", "ri.obj.42",
        ) is False


class TestUnauthenticatedDenied:
    """Unauthenticated user should be denied everything."""

    def test_no_role_denied(self) -> None:
        service = _build_service()
        assert service.check_permission("ri.user.nobody", "object_type", "read") is False
        assert service.check_permission("ri.user.nobody", "tenant", "write") is False
        assert service.check_permission("ri.user.nobody", "action", "execute") is False


class TestRoleUpdate:
    """Update a custom role and verify permission changes."""

    async def test_update_role_permissions(self) -> None:
        service = _build_service()
        session = _mock_session()

        old_role = CustomRole(
            rid="ri.role.r1",
            tenant_id="t1",
            name="limited",
            description="Limited",
            permissions=[{"resource_type": "object_type", "action": "read"}],
            is_system=False,
        )
        old_role.created_at = _now()
        old_role.updated_at = _now()

        updated_role = CustomRole(
            rid="ri.role.r1",
            tenant_id="t1",
            name="limited",
            description="Less limited",
            permissions=[
                {"resource_type": "object_type", "action": "read"},
                {"resource_type": "object_type", "action": "write"},
            ],
            is_system=False,
        )
        updated_role.created_at = _now()
        updated_role.updated_at = _now()

        with (
            patch("lingshu.setting.service.get_tenant_id", return_value="t1"),
            patch("lingshu.setting.service.CustomRoleRepository") as MockRoleRepo,
        ):
            repo = MockRoleRepo.return_value
            repo.get_by_rid = AsyncMock(return_value=old_role)
            repo.update_fields = AsyncMock(return_value=updated_role)

            # First seed old permissions
            service._enforcer.add_custom_role_policies(
                "limited", [{"resource_type": "object_type", "action": "read"}],
            )
            service._enforcer.sync_user_role("ri.user.ltd", "limited")

            # Verify initial: can read, cannot write
            assert service.check_permission("ri.user.ltd", "object_type", "read") is True
            assert service.check_permission("ri.user.ltd", "object_type", "write") is False

            # Update role
            req = UpdateRoleRequest(
                permissions=[
                    PermissionEntry(resource_type="object_type", action="read"),
                    PermissionEntry(resource_type="object_type", action="write"),
                ],
            )
            result = await service.update_role("ri.role.r1", req, session)
            assert result.name == "limited"

            # After update: can now write
            assert service.check_permission("ri.user.ltd", "object_type", "write") is True


class TestSystemRoleImmutable:
    """System roles cannot be modified."""

    async def test_update_system_role_denied(self) -> None:
        service = _build_service()
        session = _mock_session()

        system_role = CustomRole(
            rid="ri.role.sys",
            tenant_id="t1",
            name="admin",
            description="System admin",
            permissions=[{"resource_type": "*", "action": "*"}],
            is_system=True,
        )
        system_role.created_at = _now()
        system_role.updated_at = _now()

        with patch("lingshu.setting.service.CustomRoleRepository") as MockRoleRepo:
            MockRoleRepo.return_value.get_by_rid = AsyncMock(return_value=system_role)

            req = UpdateRoleRequest(name="hacked")
            with pytest.raises(AppError) as exc_info:
                await service.update_role("ri.role.sys", req, session)
            assert exc_info.value.code == ErrorCode.SETTING_PERMISSION_DENIED

    async def test_delete_system_role_denied(self) -> None:
        service = _build_service()
        session = _mock_session()

        system_role = CustomRole(
            rid="ri.role.sys",
            tenant_id="t1",
            name="admin",
            description="System admin",
            permissions=[{"resource_type": "*", "action": "*"}],
            is_system=True,
        )
        system_role.created_at = _now()
        system_role.updated_at = _now()

        with patch("lingshu.setting.service.CustomRoleRepository") as MockRoleRepo:
            MockRoleRepo.return_value.get_by_rid = AsyncMock(return_value=system_role)

            with pytest.raises(AppError) as exc_info:
                await service.delete_role("ri.role.sys", session)
            assert exc_info.value.code == ErrorCode.SETTING_PERMISSION_DENIED
