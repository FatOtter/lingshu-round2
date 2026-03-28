"""Tests for Tenant CRUD, Switch, Member Management, and RBAC integration.

These are unit tests that mock the database layer and test service logic directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.setting.auth.provider import BuiltinProvider
from lingshu.config import Settings
from lingshu.setting.authz.enforcer import PermissionEnforcer
from lingshu.setting.models import Tenant, User, UserTenantMembership
from lingshu.setting.schemas.requests import (
    AddMemberRequest,
    CreateTenantRequest,
    SwitchTenantRequest,
    UpdateMemberRoleRequest,
    UpdateTenantRequest,
)
from lingshu.setting.service import SettingServiceImpl


def _make_tenant(
    rid: str = "ri.tenant.t1",
    display_name: str = "Test Tenant",
    status: str = "active",
) -> Tenant:
    now = datetime.now(UTC)
    t = Tenant(rid=rid, display_name=display_name, status=status, config={})
    t.created_at = now
    t.updated_at = now
    return t


def _make_user(
    rid: str = "ri.user.u1",
    email: str = "user@example.com",
    display_name: str = "User",
) -> User:
    now = datetime.now(UTC)
    u = User(
        rid=rid,
        email=email,
        display_name=display_name,
        password_hash="hashed",
        status="active",
    )
    u.created_at = now
    u.updated_at = now
    return u


def _make_membership(
    user_rid: str = "ri.user.u1",
    tenant_rid: str = "ri.tenant.t1",
    role: str = "admin",
    is_default: bool = True,
) -> UserTenantMembership:
    m = UserTenantMembership(
        user_rid=user_rid,
        tenant_rid=tenant_rid,
        role=role,
        is_default=is_default,
    )
    m.created_at = datetime.now(UTC)
    return m


def _make_service() -> SettingServiceImpl:
    provider = MagicMock(spec=BuiltinProvider)
    provider.issue_access_token.return_value = "access_token_value"
    provider.issue_refresh_token.return_value = ("refresh_raw", "refresh_hash")
    provider._access_ttl = 900

    enforcer = PermissionEnforcer(settings=Settings(rbac_enabled=True))
    enforcer.seed_policies()

    return SettingServiceImpl(provider=provider, enforcer=enforcer)


@pytest.fixture
def service() -> SettingServiceImpl:
    return _make_service()


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


class TestCreateTenant:
    @pytest.mark.asyncio
    async def test_create_tenant_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenant = _make_tenant(rid="ri.tenant.new1")
        user = _make_user()

        with (
            patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
            patch("lingshu.setting.service.get_tenant_id", return_value="ri.tenant.t0"),
            patch("lingshu.setting.service.generate_rid", return_value="ri.tenant.new1"),
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
        ):
            mock_tenant_repo = MockTenantRepo.return_value
            mock_tenant_repo.create = AsyncMock(return_value=tenant)

            mock_member_repo = MockMemberRepo.return_value
            mock_member_repo.create = AsyncMock(
                return_value=_make_membership(
                    user_rid="ri.user.u1",
                    tenant_rid="ri.tenant.new1",
                    role="admin",
                )
            )

            req = CreateTenantRequest(display_name="Test Tenant")
            result = await service.create_tenant(req, mock_session)

            assert result.rid == "ri.tenant.new1"
            assert result.display_name == "Test Tenant"
            mock_tenant_repo.create.assert_awaited_once()
            mock_member_repo.create.assert_awaited_once()


class TestGetTenant:
    @pytest.mark.asyncio
    async def test_get_tenant_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenant = _make_tenant()

        with patch(
            "lingshu.setting.service.TenantRepository"
        ) as MockTenantRepo:
            mock_repo = MockTenantRepo.return_value
            mock_repo.get_by_rid = AsyncMock(return_value=tenant)

            result = await service.get_tenant("ri.tenant.t1", mock_session)
            assert result.rid == "ri.tenant.t1"
            assert result.display_name == "Test Tenant"

    @pytest.mark.asyncio
    async def test_get_tenant_not_found(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        with patch(
            "lingshu.setting.service.TenantRepository"
        ) as MockTenantRepo:
            mock_repo = MockTenantRepo.return_value
            mock_repo.get_by_rid = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.get_tenant("ri.tenant.nope", mock_session)
            assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND


class TestUpdateTenant:
    @pytest.mark.asyncio
    async def test_update_tenant_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        updated_tenant = _make_tenant(display_name="Updated")

        with patch(
            "lingshu.setting.service.TenantRepository"
        ) as MockTenantRepo:
            mock_repo = MockTenantRepo.return_value
            mock_repo.update_fields = AsyncMock(return_value=updated_tenant)

            req = UpdateTenantRequest(display_name="Updated")
            result = await service.update_tenant("ri.tenant.t1", req, mock_session)
            assert result.display_name == "Updated"

    @pytest.mark.asyncio
    async def test_update_tenant_no_fields(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        req = UpdateTenantRequest()
        with pytest.raises(AppError) as exc_info:
            await service.update_tenant("ri.tenant.t1", req, mock_session)
        assert exc_info.value.code == ErrorCode.COMMON_INVALID_INPUT


class TestDeleteTenant:
    @pytest.mark.asyncio
    async def test_delete_tenant_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        disabled_tenant = _make_tenant(status="disabled")

        with patch(
            "lingshu.setting.service.TenantRepository"
        ) as MockTenantRepo:
            mock_repo = MockTenantRepo.return_value
            mock_repo.update_fields = AsyncMock(return_value=disabled_tenant)

            await service.delete_tenant("ri.tenant.t1", mock_session)
            mock_repo.update_fields.assert_awaited_once_with(
                "ri.tenant.t1", status="disabled"
            )

    @pytest.mark.asyncio
    async def test_delete_tenant_not_found(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        with patch(
            "lingshu.setting.service.TenantRepository"
        ) as MockTenantRepo:
            mock_repo = MockTenantRepo.return_value
            mock_repo.update_fields = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.delete_tenant("ri.tenant.nope", mock_session)
            assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND


class TestQueryTenants:
    @pytest.mark.asyncio
    async def test_query_tenants_admin_sees_all(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenants = [_make_tenant(rid="ri.tenant.t1"), _make_tenant(rid="ri.tenant.t2")]

        with (
            patch("lingshu.setting.service.get_role", return_value="admin"),
            patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
        ):
            mock_repo = MockTenantRepo.return_value
            mock_repo.list_all = AsyncMock(return_value=(tenants, 2))

            result, total = await service.query_tenants(mock_session)
            assert total == 2
            assert len(result) == 2
            mock_repo.list_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_tenants_member_sees_own(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenants = [_make_tenant(rid="ri.tenant.t1")]

        with (
            patch("lingshu.setting.service.get_role", return_value="member"),
            patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
        ):
            mock_repo = MockTenantRepo.return_value
            mock_repo.list_by_user = AsyncMock(return_value=(tenants, 1))

            result, total = await service.query_tenants(mock_session)
            assert total == 1
            mock_repo.list_by_user.assert_awaited_once_with(
                "ri.user.u1", offset=0, limit=20
            )


class TestSwitchTenant:
    @pytest.mark.asyncio
    async def test_switch_tenant_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenant = _make_tenant(rid="ri.tenant.t2")
        membership = _make_membership(
            user_rid="ri.user.u1", tenant_rid="ri.tenant.t2", role="member"
        )

        with (
            patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.RefreshTokenRepository"
            ) as MockRefreshRepo,
        ):
            MockMemberRepo.return_value.get = AsyncMock(return_value=membership)
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=tenant)
            MockRefreshRepo.return_value.create = AsyncMock()

            req = SwitchTenantRequest(tenant_rid="ri.tenant.t2")
            access, refresh, role = await service.switch_tenant(req, mock_session)

            assert access == "access_token_value"
            assert refresh == "refresh_raw"
            assert role == "member"

    @pytest.mark.asyncio
    async def test_switch_tenant_not_a_member(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        with (
            patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.RefreshTokenRepository"
            ),
        ):
            MockMemberRepo.return_value.get = AsyncMock(return_value=None)
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=None)

            req = SwitchTenantRequest(tenant_rid="ri.tenant.t99")
            with pytest.raises(AppError) as exc_info:
                await service.switch_tenant(req, mock_session)
            assert exc_info.value.code == ErrorCode.SETTING_PERMISSION_DENIED

    @pytest.mark.asyncio
    async def test_switch_tenant_disabled(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        membership = _make_membership(
            user_rid="ri.user.u1", tenant_rid="ri.tenant.t2", role="member"
        )
        disabled_tenant = _make_tenant(rid="ri.tenant.t2", status="disabled")

        with (
            patch("lingshu.setting.service.get_user_id", return_value="ri.user.u1"),
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.RefreshTokenRepository"
            ),
        ):
            MockMemberRepo.return_value.get = AsyncMock(return_value=membership)
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=disabled_tenant)

            req = SwitchTenantRequest(tenant_rid="ri.tenant.t2")
            with pytest.raises(AppError) as exc_info:
                await service.switch_tenant(req, mock_session)
            assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND


class TestAddMember:
    @pytest.mark.asyncio
    async def test_add_member_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenant = _make_tenant()
        user = _make_user(rid="ri.user.u2", email="new@example.com")
        membership = _make_membership(
            user_rid="ri.user.u2", tenant_rid="ri.tenant.t1", role="member"
        )

        with (
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.UserRepository"
            ) as MockUserRepo,
        ):
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=tenant)
            MockUserRepo.return_value.get_by_rid = AsyncMock(return_value=user)
            MockMemberRepo.return_value.get = AsyncMock(return_value=None)
            MockMemberRepo.return_value.create = AsyncMock(return_value=membership)

            req = AddMemberRequest(user_rid="ri.user.u2", role="member")
            result = await service.add_member("ri.tenant.t1", req, mock_session)

            assert result.user_rid == "ri.user.u2"
            assert result.role == "member"

    @pytest.mark.asyncio
    async def test_add_member_already_exists(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenant = _make_tenant()
        user = _make_user(rid="ri.user.u2")
        existing = _make_membership(user_rid="ri.user.u2")

        with (
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.UserRepository"
            ) as MockUserRepo,
        ):
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=tenant)
            MockUserRepo.return_value.get_by_rid = AsyncMock(return_value=user)
            MockMemberRepo.return_value.get = AsyncMock(return_value=existing)

            req = AddMemberRequest(user_rid="ri.user.u2")
            with pytest.raises(AppError) as exc_info:
                await service.add_member("ri.tenant.t1", req, mock_session)
            assert exc_info.value.code == ErrorCode.COMMON_CONFLICT

    @pytest.mark.asyncio
    async def test_add_member_user_not_found(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenant = _make_tenant()

        with (
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.UserRepository"
            ) as MockUserRepo,
        ):
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=tenant)
            MockUserRepo.return_value.get_by_rid = AsyncMock(return_value=None)
            MockMemberRepo.return_value.get = AsyncMock(return_value=None)

            req = AddMemberRequest(user_rid="ri.user.nonexistent")
            with pytest.raises(AppError) as exc_info:
                await service.add_member("ri.tenant.t1", req, mock_session)
            assert exc_info.value.code == ErrorCode.SETTING_USER_NOT_FOUND


class TestUpdateMemberRole:
    @pytest.mark.asyncio
    async def test_update_role_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        membership = _make_membership(role="member")
        updated_membership = _make_membership(role="admin")
        user = _make_user()

        with (
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
            patch(
                "lingshu.setting.service.UserRepository"
            ) as MockUserRepo,
        ):
            mock_member_repo = MockMemberRepo.return_value
            mock_member_repo.get = AsyncMock(return_value=membership)
            mock_member_repo.update_role = AsyncMock(return_value=updated_membership)
            MockUserRepo.return_value.get_by_rid = AsyncMock(return_value=user)

            req = UpdateMemberRoleRequest(role="admin")
            result = await service.update_member_role(
                "ri.tenant.t1", "ri.user.u1", req, mock_session
            )
            assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_update_role_membership_not_found(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        with patch(
            "lingshu.setting.service.MembershipRepository"
        ) as MockMemberRepo:
            MockMemberRepo.return_value.get = AsyncMock(return_value=None)

            req = UpdateMemberRoleRequest(role="admin")
            with pytest.raises(AppError) as exc_info:
                await service.update_member_role(
                    "ri.tenant.t1", "ri.user.nobody", req, mock_session
                )
            assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND


class TestRemoveMember:
    @pytest.mark.asyncio
    async def test_remove_member_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        membership = _make_membership(role="member")

        with patch(
            "lingshu.setting.service.MembershipRepository"
        ) as MockMemberRepo:
            mock_repo = MockMemberRepo.return_value
            mock_repo.get = AsyncMock(return_value=membership)
            mock_repo.delete = AsyncMock()

            await service.remove_member("ri.tenant.t1", "ri.user.u1", mock_session)
            mock_repo.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_last_admin_blocked(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        membership = _make_membership(role="admin")
        # Only one admin in the tenant
        all_members = [membership]

        with patch(
            "lingshu.setting.service.MembershipRepository"
        ) as MockMemberRepo:
            mock_repo = MockMemberRepo.return_value
            mock_repo.get = AsyncMock(return_value=membership)
            mock_repo.list_by_tenant = AsyncMock(return_value=(all_members, 1))

            with pytest.raises(AppError) as exc_info:
                await service.remove_member("ri.tenant.t1", "ri.user.u1", mock_session)
            assert exc_info.value.code == ErrorCode.COMMON_INVALID_INPUT

    @pytest.mark.asyncio
    async def test_remove_admin_when_multiple_admins_allowed(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        membership = _make_membership(role="admin")
        other_admin = _make_membership(user_rid="ri.user.u2", role="admin")
        all_members = [membership, other_admin]

        with patch(
            "lingshu.setting.service.MembershipRepository"
        ) as MockMemberRepo:
            mock_repo = MockMemberRepo.return_value
            mock_repo.get = AsyncMock(return_value=membership)
            mock_repo.list_by_tenant = AsyncMock(return_value=(all_members, 2))
            mock_repo.delete = AsyncMock()

            await service.remove_member("ri.tenant.t1", "ri.user.u1", mock_session)
            mock_repo.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_member_not_found(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        with patch(
            "lingshu.setting.service.MembershipRepository"
        ) as MockMemberRepo:
            MockMemberRepo.return_value.get = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.remove_member("ri.tenant.t1", "ri.user.nope", mock_session)
            assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND


class TestQueryMembers:
    @pytest.mark.asyncio
    async def test_query_members_success(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        tenant = _make_tenant()
        user = _make_user()
        membership = _make_membership()

        with (
            patch(
                "lingshu.setting.service.MembershipRepository"
            ) as MockMemberRepo,
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.UserRepository"
            ) as MockUserRepo,
        ):
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=tenant)
            MockMemberRepo.return_value.list_by_tenant = AsyncMock(
                return_value=([membership], 1)
            )
            MockUserRepo.return_value.get_by_rid = AsyncMock(return_value=user)

            result, total = await service.query_members("ri.tenant.t1", mock_session)
            assert total == 1
            assert len(result) == 1
            assert result[0].user_rid == "ri.user.u1"

    @pytest.mark.asyncio
    async def test_query_members_tenant_not_found(
        self, service: SettingServiceImpl, mock_session: AsyncMock
    ):
        with (
            patch(
                "lingshu.setting.service.MembershipRepository"
            ),
            patch(
                "lingshu.setting.service.TenantRepository"
            ) as MockTenantRepo,
            patch(
                "lingshu.setting.service.UserRepository"
            ),
        ):
            MockTenantRepo.return_value.get_by_rid = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.query_members("ri.tenant.nope", mock_session)
            assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND


class TestRBACPermissionCheck:
    """Integration-style tests that verify the enforcer is used by the service."""

    def test_admin_permission_via_service(self, service: SettingServiceImpl):
        service._enforcer.sync_user_role("ri.user.admin1", "admin")
        assert service.check_permission("ri.user.admin1", "tenant", "write") is True
        assert service.check_permission("ri.user.admin1", "user", "delete") is True

    def test_member_permission_via_service(self, service: SettingServiceImpl):
        service._enforcer.sync_user_role("ri.user.member1", "member")
        assert service.check_permission("ri.user.member1", "object_type", "read") is True
        assert service.check_permission("ri.user.member1", "object_type", "create") is True
        assert service.check_permission("ri.user.member1", "user", "create") is False

    def test_viewer_permission_via_service(self, service: SettingServiceImpl):
        service._enforcer.sync_user_role("ri.user.viewer1", "viewer")
        assert service.check_permission("ri.user.viewer1", "object_type", "read") is True
        assert service.check_permission("ri.user.viewer1", "object_type", "create") is False
        assert service.check_permission("ri.user.viewer1", "action", "execute") is False

    def test_unauthenticated_denied(self, service: SettingServiceImpl):
        assert service.check_permission("ri.user.nobody", "object_type", "read") is False
