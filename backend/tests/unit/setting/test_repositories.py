"""Unit tests for all Setting module repositories using mocked AsyncSession."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

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


# ── Helpers ────────────────────────────────────────────────────────


def _make_session() -> AsyncMock:
    """Create a mock AsyncSession with common methods."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    return session


def _mock_execute_scalar(session: AsyncMock, value):
    """Configure session.execute to return scalar_one_or_none with value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute = AsyncMock(return_value=result)


def _mock_execute_scalars_list(session: AsyncMock, values: list):
    """Configure session.execute to return scalars().all() with values."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = values
    result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result)


def _mock_execute_scalar_one(session: AsyncMock, value):
    """Configure session.execute to return scalar_one with value."""
    result = MagicMock()
    result.scalar_one.return_value = value
    session.execute = AsyncMock(return_value=result)


# ══════════════════════════════════════════════════════════════════
# AuditLogRepository
# ══════════════════════════════════════════════════════════════════


class TestAuditLogRepository:
    @pytest.fixture
    def session(self) -> AsyncMock:
        return _make_session()

    @pytest.fixture
    def repo(self, session: AsyncMock) -> AuditLogRepository:
        return AuditLogRepository(session)

    @pytest.mark.asyncio
    async def test_create(self, repo: AuditLogRepository, session: AsyncMock):
        log = AuditLog(
            tenant_id="t1", module="setting", event_type="test",
            user_id="u1", action="test_action",
        )
        result = await repo.create(log)
        session.add.assert_called_once_with(log)
        session.flush.assert_awaited_once()
        assert result is log

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repo: AuditLogRepository, session: AsyncMock):
        log = AuditLog(log_id=1, tenant_id="t1", module="m", event_type="e", user_id="u", action="a")
        _mock_execute_scalar(session, log)
        result = await repo.get_by_id(1, "t1")
        assert result is log

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo: AuditLogRepository, session: AsyncMock):
        _mock_execute_scalar(session, None)
        result = await repo.get_by_id(999, "t1")
        assert result is None

    @pytest.mark.asyncio
    async def test_query_with_all_filters(self, repo: AuditLogRepository, session: AsyncMock):
        log = AuditLog(log_id=1, tenant_id="t1", module="setting", event_type="create",
                       user_id="u1", action="a", resource_type="user", resource_rid="ri.user.1")
        # Two execute calls: count then data
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [log]
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        logs, total = await repo.query(
            "t1", module="setting", event_type="create",
            user_id="u1", resource_type="user", resource_rid="ri.user.1",
        )
        assert total == 1
        assert len(logs) == 1
        assert logs[0] is log

    @pytest.mark.asyncio
    async def test_query_no_filters(self, repo: AuditLogRepository, session: AsyncMock):
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        logs, total = await repo.query("t1")
        assert total == 0
        assert logs == []

    @pytest.mark.asyncio
    async def test_delete_before(self, repo: AuditLogRepository, session: AsyncMock):
        count_result = MagicMock()
        count_result.scalar_one.return_value = 5
        session.execute = AsyncMock(side_effect=[count_result, AsyncMock(), None])

        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
        count = await repo.delete_before("t1", cutoff)
        assert count == 5
        session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_recent(self, repo: AuditLogRepository, session: AsyncMock):
        logs = [
            AuditLog(log_id=i, tenant_id="t1", module="m", event_type="e", user_id="u", action="a")
            for i in range(3)
        ]
        _mock_execute_scalars_list(session, logs)
        result = await repo.recent("t1", limit=3)
        assert len(result) == 3


# ══════════════════════════════════════════════════════════════════
# MembershipRepository
# ══════════════════════════════════════════════════════════════════


class TestMembershipRepository:
    @pytest.fixture
    def session(self) -> AsyncMock:
        return _make_session()

    @pytest.fixture
    def repo(self, session: AsyncMock) -> MembershipRepository:
        return MembershipRepository(session)

    @pytest.mark.asyncio
    async def test_create(self, repo: MembershipRepository, session: AsyncMock):
        m = UserTenantMembership(user_rid="u1", tenant_rid="t1", role="admin", is_default=True)
        result = await repo.create(m)
        session.add.assert_called_once_with(m)
        assert result is m

    @pytest.mark.asyncio
    async def test_get_found(self, repo: MembershipRepository, session: AsyncMock):
        m = UserTenantMembership(user_rid="u1", tenant_rid="t1", role="admin")
        _mock_execute_scalar(session, m)
        result = await repo.get("u1", "t1")
        assert result is m

    @pytest.mark.asyncio
    async def test_get_not_found(self, repo: MembershipRepository, session: AsyncMock):
        _mock_execute_scalar(session, None)
        assert await repo.get("u1", "t1") is None

    @pytest.mark.asyncio
    async def test_get_default_tenant(self, repo: MembershipRepository, session: AsyncMock):
        m = UserTenantMembership(user_rid="u1", tenant_rid="t1", role="admin", is_default=True)
        _mock_execute_scalar(session, m)
        result = await repo.get_default_tenant("u1")
        assert result is m

    @pytest.mark.asyncio
    async def test_list_by_user(self, repo: MembershipRepository, session: AsyncMock):
        memberships = [
            UserTenantMembership(user_rid="u1", tenant_rid=f"t{i}", role="member")
            for i in range(2)
        ]
        _mock_execute_scalars_list(session, memberships)
        result = await repo.list_by_user("u1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, repo: MembershipRepository, session: AsyncMock):
        memberships = [UserTenantMembership(user_rid="u1", tenant_rid="t1", role="admin")]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = memberships
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_by_tenant("t1")
        assert total == 1
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_update_role(self, repo: MembershipRepository, session: AsyncMock):
        updated = UserTenantMembership(user_rid="u1", tenant_rid="t1", role="viewer")
        # update_role calls execute (update), flush, then get (execute again)
        _mock_execute_scalar(session, updated)
        # We need to handle multiple execute calls
        first_exec = AsyncMock()  # for update
        second_exec_result = MagicMock()
        second_exec_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[first_exec, second_exec_result])

        result = await repo.update_role("u1", "t1", "viewer")
        assert result is updated

    @pytest.mark.asyncio
    async def test_delete(self, repo: MembershipRepository, session: AsyncMock):
        await repo.delete("u1", "t1")
        session.execute.assert_awaited()
        session.flush.assert_awaited()


# ══════════════════════════════════════════════════════════════════
# CustomRoleRepository
# ══════════════════════════════════════════════════════════════════


class TestCustomRoleRepository:
    @pytest.fixture
    def session(self) -> AsyncMock:
        return _make_session()

    @pytest.fixture
    def repo(self, session: AsyncMock) -> CustomRoleRepository:
        return CustomRoleRepository(session)

    @pytest.mark.asyncio
    async def test_create(self, repo: CustomRoleRepository, session: AsyncMock):
        role = CustomRole(
            rid="ri.role.1", tenant_id="t1", name="editor",
            permissions=[{"resource_type": "*", "action": "read"}],
        )
        result = await repo.create(role)
        session.add.assert_called_once_with(role)
        assert result is role

    @pytest.mark.asyncio
    async def test_get_by_rid(self, repo: CustomRoleRepository, session: AsyncMock):
        role = CustomRole(rid="ri.role.1", tenant_id="t1", name="editor", permissions=[])
        _mock_execute_scalar(session, role)
        result = await repo.get_by_rid("ri.role.1")
        assert result is role

    @pytest.mark.asyncio
    async def test_get_by_name(self, repo: CustomRoleRepository, session: AsyncMock):
        role = CustomRole(rid="ri.role.1", tenant_id="t1", name="editor", permissions=[])
        _mock_execute_scalar(session, role)
        result = await repo.get_by_name("t1", "editor")
        assert result is role

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, repo: CustomRoleRepository, session: AsyncMock):
        roles = [
            CustomRole(rid=f"ri.role.{i}", tenant_id="t1", name=f"role_{i}", permissions=[])
            for i in range(3)
        ]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = roles
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_by_tenant("t1")
        assert total == 3
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_update_fields_empty(self, repo: CustomRoleRepository, session: AsyncMock):
        role = CustomRole(rid="ri.role.1", tenant_id="t1", name="editor", permissions=[])
        _mock_execute_scalar(session, role)
        result = await repo.update_fields("ri.role.1")
        assert result is role

    @pytest.mark.asyncio
    async def test_update_fields_with_data(self, repo: CustomRoleRepository, session: AsyncMock):
        updated = CustomRole(rid="ri.role.1", tenant_id="t1", name="new_name", permissions=[])
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[exec_result, get_result])

        result = await repo.update_fields("ri.role.1", name="new_name")
        assert result is updated

    @pytest.mark.asyncio
    async def test_delete(self, repo: CustomRoleRepository, session: AsyncMock):
        await repo.delete("ri.role.1")
        session.execute.assert_awaited()
        session.flush.assert_awaited()


# ══════════════════════════════════════════════════════════════════
# TenantRepository
# ══════════════════════════════════════════════════════════════════


class TestTenantRepository:
    @pytest.fixture
    def session(self) -> AsyncMock:
        return _make_session()

    @pytest.fixture
    def repo(self, session: AsyncMock) -> TenantRepository:
        return TenantRepository(session)

    @pytest.mark.asyncio
    async def test_create(self, repo: TenantRepository, session: AsyncMock):
        tenant = Tenant(rid="ri.tenant.1", display_name="Test")
        result = await repo.create(tenant)
        session.add.assert_called_once_with(tenant)
        assert result is tenant

    @pytest.mark.asyncio
    async def test_get_by_rid(self, repo: TenantRepository, session: AsyncMock):
        tenant = Tenant(rid="ri.tenant.1", display_name="Test")
        _mock_execute_scalar(session, tenant)
        result = await repo.get_by_rid("ri.tenant.1")
        assert result is tenant

    @pytest.mark.asyncio
    async def test_get_by_rid_not_found(self, repo: TenantRepository, session: AsyncMock):
        _mock_execute_scalar(session, None)
        result = await repo.get_by_rid("ri.tenant.999")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, repo: TenantRepository, session: AsyncMock):
        tenants = [Tenant(rid=f"ri.tenant.{i}", display_name=f"T{i}") for i in range(2)]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = tenants
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_all()
        assert total == 2
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_user(self, repo: TenantRepository, session: AsyncMock):
        tenants = [Tenant(rid="ri.tenant.1", display_name="T1")]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = tenants
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_by_user("u1")
        assert total == 1
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_update_fields(self, repo: TenantRepository, session: AsyncMock):
        updated = Tenant(rid="ri.tenant.1", display_name="Updated")
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[exec_result, get_result])

        result = await repo.update_fields("ri.tenant.1", display_name="Updated")
        assert result is updated

    @pytest.mark.asyncio
    async def test_count(self, repo: TenantRepository, session: AsyncMock):
        _mock_execute_scalar_one(session, 5)
        result = await repo.count()
        assert result == 5


# ══════════════════════════════════════════════════════════════════
# UserRepository
# ══════════════════════════════════════════════════════════════════


class TestUserRepository:
    @pytest.fixture
    def session(self) -> AsyncMock:
        return _make_session()

    @pytest.fixture
    def repo(self, session: AsyncMock) -> UserRepository:
        return UserRepository(session)

    @pytest.mark.asyncio
    async def test_create(self, repo: UserRepository, session: AsyncMock):
        user = User(rid="ri.user.1", email="a@b.com", display_name="A", password_hash="h")
        result = await repo.create(user)
        session.add.assert_called_once_with(user)
        assert result is user

    @pytest.mark.asyncio
    async def test_get_by_rid(self, repo: UserRepository, session: AsyncMock):
        user = User(rid="ri.user.1", email="a@b.com", display_name="A", password_hash="h")
        _mock_execute_scalar(session, user)
        result = await repo.get_by_rid("ri.user.1")
        assert result is user

    @pytest.mark.asyncio
    async def test_get_by_email(self, repo: UserRepository, session: AsyncMock):
        user = User(rid="ri.user.1", email="a@b.com", display_name="A", password_hash="h")
        _mock_execute_scalar(session, user)
        result = await repo.get_by_email("a@b.com")
        assert result is user

    @pytest.mark.asyncio
    async def test_get_by_email_not_found(self, repo: UserRepository, session: AsyncMock):
        _mock_execute_scalar(session, None)
        assert await repo.get_by_email("no@b.com") is None

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, repo: UserRepository, session: AsyncMock):
        users = [User(rid=f"ri.user.{i}", email=f"u{i}@b.com", display_name=f"U{i}", password_hash="h") for i in range(2)]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = users
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_by_tenant("t1")
        assert total == 2
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_update_fields(self, repo: UserRepository, session: AsyncMock):
        updated = User(rid="ri.user.1", email="a@b.com", display_name="New", password_hash="h")
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[exec_result, get_result])

        result = await repo.update_fields("ri.user.1", display_name="New")
        assert result is updated

    @pytest.mark.asyncio
    async def test_count(self, repo: UserRepository, session: AsyncMock):
        _mock_execute_scalar_one(session, 10)
        result = await repo.count()
        assert result == 10

    @pytest.mark.asyncio
    async def test_count_by_status(self, repo: UserRepository, session: AsyncMock):
        result_mock = MagicMock()
        result_mock.all.return_value = [("active", 5), ("disabled", 2)]
        session.execute = AsyncMock(return_value=result_mock)

        result = await repo.count_by_status("t1")
        assert result == {"active": 5, "disabled": 2}


# ══════════════════════════════════════════════════════════════════
# RefreshTokenRepository
# ══════════════════════════════════════════════════════════════════


class TestRefreshTokenRepository:
    @pytest.fixture
    def session(self) -> AsyncMock:
        return _make_session()

    @pytest.fixture
    def repo(self, session: AsyncMock) -> RefreshTokenRepository:
        return RefreshTokenRepository(session)

    @pytest.mark.asyncio
    async def test_create(self, repo: RefreshTokenRepository, session: AsyncMock):
        token = RefreshToken(
            token_hash="abc", user_rid="u1", tenant_rid="t1",
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        result = await repo.create(token)
        session.add.assert_called_once_with(token)
        assert result is token

    @pytest.mark.asyncio
    async def test_get_by_hash_found(self, repo: RefreshTokenRepository, session: AsyncMock):
        token = RefreshToken(
            token_hash="abc", user_rid="u1", tenant_rid="t1",
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        _mock_execute_scalar(session, token)
        result = await repo.get_by_hash("abc")
        assert result is token

    @pytest.mark.asyncio
    async def test_get_by_hash_not_found(self, repo: RefreshTokenRepository, session: AsyncMock):
        _mock_execute_scalar(session, None)
        assert await repo.get_by_hash("missing") is None

    @pytest.mark.asyncio
    async def test_revoke(self, repo: RefreshTokenRepository, session: AsyncMock):
        await repo.revoke("abc")
        session.execute.assert_awaited()
        session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_revoke_all_for_user(self, repo: RefreshTokenRepository, session: AsyncMock):
        await repo.revoke_all_for_user("u1", "t1")
        session.execute.assert_awaited()
        session.flush.assert_awaited()

    def test_is_valid_true(self, repo: RefreshTokenRepository):
        # is_valid uses datetime.utcnow() (naive), so use naive datetimes here
        token = RefreshToken(
            token_hash="abc", user_rid="u1", tenant_rid="t1",
            expires_at=datetime(2030, 1, 1),
            revoked_at=None,
        )
        assert repo.is_valid(token) is True

    def test_is_valid_revoked(self, repo: RefreshTokenRepository):
        token = RefreshToken(
            token_hash="abc", user_rid="u1", tenant_rid="t1",
            expires_at=datetime(2030, 1, 1),
            revoked_at=datetime(2025, 1, 1),
        )
        assert repo.is_valid(token) is False

    def test_is_valid_expired(self, repo: RefreshTokenRepository):
        token = RefreshToken(
            token_hash="abc", user_rid="u1", tenant_rid="t1",
            expires_at=datetime(2020, 1, 1),
            revoked_at=None,
        )
        assert repo.is_valid(token) is False
