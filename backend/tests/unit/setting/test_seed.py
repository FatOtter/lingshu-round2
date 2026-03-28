"""Unit tests for setting/seed.py — run_seed and _seed_system_roles."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.setting.seed import run_seed


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    return session


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.seed_admin_email = "admin@example.com"
    settings.seed_admin_password = "secret123"
    settings.seed_tenant_name = "Default"
    return settings


@pytest.fixture
def mock_enforcer() -> MagicMock:
    enforcer = MagicMock()
    enforcer.seed_policies = MagicMock()
    enforcer.sync_user_role = MagicMock()
    enforcer.add_custom_role_policies = MagicMock()
    return enforcer


@pytest.mark.asyncio
async def test_run_seed_creates_admin_when_empty(
    mock_session: AsyncMock, mock_settings: MagicMock, mock_enforcer: MagicMock
) -> None:
    """run_seed() should create admin user, tenant, and membership when DB is empty."""
    user_check = MagicMock()
    user_check.scalar_one_or_none.return_value = None

    role_check = MagicMock()
    role_check.scalar_one_or_none.return_value = None

    call_count = 0

    async def execute_side_effect(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return user_check
        return role_check

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("lingshu.setting.seed.hash_password", return_value="hashed"):
        with patch("lingshu.setting.seed.generate_rid", side_effect=[
            "ri.tenant.t1", "ri.user.u1", "ri.role.r1", "ri.role.r2", "ri.role.r3"
        ]):
            await run_seed(mock_session, mock_settings, mock_enforcer)

    mock_enforcer.seed_policies.assert_called_once()
    assert mock_session.add.call_count >= 4
    mock_session.commit.assert_awaited_once()
    mock_enforcer.sync_user_role.assert_called_once_with("ri.user.u1", "admin")


@pytest.mark.asyncio
async def test_run_seed_idempotent_skips_when_users_exist(
    mock_session: AsyncMock, mock_settings: MagicMock, mock_enforcer: MagicMock
) -> None:
    """run_seed() should skip creation if users already exist."""
    user_check = MagicMock()
    user_check.scalar_one_or_none.return_value = MagicMock()  # user exists

    membership_scalars = MagicMock()
    membership_scalars.all.return_value = []
    membership_result = MagicMock()
    membership_result.scalars.return_value = membership_scalars

    tenant_result = MagicMock()
    tenant_result.all.return_value = []

    custom_roles_scalars = MagicMock()
    custom_roles_scalars.all.return_value = []
    custom_roles_result = MagicMock()
    custom_roles_result.scalars.return_value = custom_roles_scalars

    mock_session.execute = AsyncMock(side_effect=[
        user_check, membership_result, tenant_result, custom_roles_result,
    ])

    await run_seed(mock_session, mock_settings, mock_enforcer)

    mock_enforcer.seed_policies.assert_called_once()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_seed_syncs_existing_roles_on_rerun(
    mock_session: AsyncMock, mock_settings: MagicMock, mock_enforcer: MagicMock
) -> None:
    """run_seed() should sync existing membership roles to enforcer on re-run."""
    user_check = MagicMock()
    user_check.scalar_one_or_none.return_value = MagicMock()

    membership = MagicMock()
    membership.user_rid = "ri.user.u1"
    membership.role = "admin"
    membership_scalars = MagicMock()
    membership_scalars.all.return_value = [membership]
    membership_result = MagicMock()
    membership_result.scalars.return_value = membership_scalars

    tenant_result = MagicMock()
    tenant_result.all.return_value = []

    custom_roles_scalars = MagicMock()
    custom_roles_scalars.all.return_value = []
    custom_roles_result = MagicMock()
    custom_roles_result.scalars.return_value = custom_roles_scalars

    mock_session.execute = AsyncMock(side_effect=[
        user_check, membership_result, tenant_result, custom_roles_result,
    ])

    await run_seed(mock_session, mock_settings, mock_enforcer)

    mock_enforcer.sync_user_role.assert_called_once_with("ri.user.u1", "admin")


@pytest.mark.asyncio
async def test_run_seed_always_seeds_policies(
    mock_session: AsyncMock, mock_settings: MagicMock, mock_enforcer: MagicMock
) -> None:
    """run_seed() should always call seed_policies regardless of DB state."""
    user_check = MagicMock()
    user_check.scalar_one_or_none.return_value = MagicMock()

    membership_scalars = MagicMock()
    membership_scalars.all.return_value = []
    membership_result = MagicMock()
    membership_result.scalars.return_value = membership_scalars

    tenant_result = MagicMock()
    tenant_result.all.return_value = []

    custom_roles_scalars = MagicMock()
    custom_roles_scalars.all.return_value = []
    custom_roles_result = MagicMock()
    custom_roles_result.scalars.return_value = custom_roles_scalars

    mock_session.execute = AsyncMock(side_effect=[
        user_check, membership_result, tenant_result, custom_roles_result,
    ])

    await run_seed(mock_session, mock_settings, mock_enforcer)

    mock_enforcer.seed_policies.assert_called_once()


@pytest.mark.asyncio
async def test_run_seed_syncs_custom_roles(
    mock_session: AsyncMock, mock_settings: MagicMock, mock_enforcer: MagicMock
) -> None:
    """run_seed() should sync non-system custom role policies to enforcer."""
    user_check = MagicMock()
    user_check.scalar_one_or_none.return_value = MagicMock()

    membership_scalars = MagicMock()
    membership_scalars.all.return_value = []
    membership_result = MagicMock()
    membership_result.scalars.return_value = membership_scalars

    tenant_result = MagicMock()
    tenant_result.all.return_value = []

    cr = MagicMock()
    cr.is_system = False
    cr.name = "editor"
    cr.permissions = [{"resource_type": "*", "action": "read"}]
    custom_roles_scalars = MagicMock()
    custom_roles_scalars.all.return_value = [cr]
    custom_roles_result = MagicMock()
    custom_roles_result.scalars.return_value = custom_roles_scalars

    mock_session.execute = AsyncMock(side_effect=[
        user_check, membership_result, tenant_result, custom_roles_result,
    ])

    await run_seed(mock_session, mock_settings, mock_enforcer)

    mock_enforcer.add_custom_role_policies.assert_called_once_with(
        "editor", [{"resource_type": "*", "action": "read"}]
    )


@pytest.mark.asyncio
async def test_run_seed_skips_system_custom_roles(
    mock_session: AsyncMock, mock_settings: MagicMock, mock_enforcer: MagicMock
) -> None:
    """System custom roles (is_system=True) should NOT be synced to enforcer."""
    user_check = MagicMock()
    user_check.scalar_one_or_none.return_value = MagicMock()

    membership_scalars = MagicMock()
    membership_scalars.all.return_value = []
    membership_result = MagicMock()
    membership_result.scalars.return_value = membership_scalars

    tenant_result = MagicMock()
    tenant_result.all.return_value = []

    cr = MagicMock()
    cr.is_system = True
    cr.name = "admin"
    cr.permissions = [{"resource_type": "*", "action": "*"}]
    custom_roles_scalars = MagicMock()
    custom_roles_scalars.all.return_value = [cr]
    custom_roles_result = MagicMock()
    custom_roles_result.scalars.return_value = custom_roles_scalars

    mock_session.execute = AsyncMock(side_effect=[
        user_check, membership_result, tenant_result, custom_roles_result,
    ])

    await run_seed(mock_session, mock_settings, mock_enforcer)

    mock_enforcer.add_custom_role_policies.assert_not_called()


@pytest.mark.asyncio
async def test_seed_system_roles_with_existing_tenant(
    mock_session: AsyncMock, mock_settings: MagicMock, mock_enforcer: MagicMock
) -> None:
    """When users exist, _seed_system_roles should check all existing tenants."""
    user_check = MagicMock()
    user_check.scalar_one_or_none.return_value = MagicMock()

    membership_scalars = MagicMock()
    membership_scalars.all.return_value = []
    membership_result = MagicMock()
    membership_result.scalars.return_value = membership_scalars

    # Two tenants
    tenant_result = MagicMock()
    tenant_result.all.return_value = [("t1",), ("t2",)]

    # Role checks for each tenant x 3 system roles = 6 checks
    role_exists = MagicMock()
    role_exists.scalar_one_or_none.return_value = MagicMock()  # already exist

    custom_roles_scalars = MagicMock()
    custom_roles_scalars.all.return_value = []
    custom_roles_result = MagicMock()
    custom_roles_result.scalars.return_value = custom_roles_scalars

    mock_session.execute = AsyncMock(side_effect=[
        user_check, membership_result, tenant_result,
        role_exists, role_exists, role_exists,  # t1's 3 roles
        role_exists, role_exists, role_exists,  # t2's 3 roles
        custom_roles_result,
    ])

    await run_seed(mock_session, mock_settings, mock_enforcer)

    # No new roles should be added since they all exist
    add_calls = [c for c in mock_session.add.call_args_list
                 if hasattr(c[0][0], 'is_system')]
    assert len(add_calls) == 0


@pytest.mark.asyncio
async def test_seed_uses_correct_admin_settings(
    mock_session: AsyncMock, mock_enforcer: MagicMock
) -> None:
    """Admin user should use the email/password from settings."""
    settings = MagicMock()
    settings.seed_admin_email = "custom@admin.com"
    settings.seed_admin_password = "CustomPass123!"
    settings.seed_tenant_name = "CustomTenant"

    user_check = MagicMock()
    user_check.scalar_one_or_none.return_value = None

    role_check = MagicMock()
    role_check.scalar_one_or_none.return_value = None

    call_count = 0

    async def execute_side_effect(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return user_check
        return role_check

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("lingshu.setting.seed.hash_password", return_value="hashed") as mock_hash:
        with patch("lingshu.setting.seed.generate_rid", side_effect=[
            "ri.tenant.t1", "ri.user.u1", "ri.role.r1", "ri.role.r2", "ri.role.r3"
        ]):
            await run_seed(mock_session, settings, mock_enforcer)

    mock_hash.assert_called_once_with("CustomPass123!")

    # Find the user object that was added
    user_added = None
    tenant_added = None
    for call in mock_session.add.call_args_list:
        obj = call[0][0]
        if hasattr(obj, "email"):
            user_added = obj
        if hasattr(obj, "display_name") and not hasattr(obj, "email"):
            tenant_added = obj

    assert user_added is not None
    assert user_added.email == "custom@admin.com"
    assert tenant_added is not None
    assert tenant_added.display_name == "CustomTenant"
