"""IT-05: Integration tests for RBAC across modules."""

from __future__ import annotations

from lingshu.setting.authz.enforcer import PermissionEnforcer


# ── Helpers ───────────────────────────────────────────────────────


def _make_enforcer(*, rbac_enabled: bool = True) -> PermissionEnforcer:
    """Create an enforcer with RBAC enabled/disabled and seeded policies."""
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.rbac_enabled = rbac_enabled
    enforcer = PermissionEnforcer(settings=settings)
    enforcer.seed_policies()
    return enforcer


# ── Tests ─────────────────────────────────────────────────────────


class TestViewerCanReadOntologyNotWrite:
    """Viewer role should allow read but deny write on ontology resources."""

    async def test_viewer_can_read_ontology_not_write(self) -> None:
        enforcer = _make_enforcer(rbac_enabled=True)
        enforcer.sync_user_role("ri.user.viewer1", "viewer")

        # Read should succeed
        assert enforcer.check_permission(
            "ri.user.viewer1", "object_type", "read"
        ) is True

        # Write should fail
        assert enforcer.check_permission(
            "ri.user.viewer1", "object_type", "write"
        ) is False

        # Create should fail
        assert enforcer.check_permission(
            "ri.user.viewer1", "object_type", "create"
        ) is False

        # Delete should fail
        assert enforcer.check_permission(
            "ri.user.viewer1", "object_type", "delete"
        ) is False


class TestMemberCanCreateOntologyNotManageUsers:
    """Member role should create ontology entities but not manage users."""

    async def test_member_can_create_ontology_not_manage_users(self) -> None:
        enforcer = _make_enforcer(rbac_enabled=True)
        enforcer.sync_user_role("ri.user.member1", "member")

        # Create object_type → allowed for member
        assert enforcer.check_permission(
            "ri.user.member1", "object_type", "create"
        ) is True

        # Update link_type → allowed
        assert enforcer.check_permission(
            "ri.user.member1", "link_type", "update"
        ) is True

        # Read → allowed for member
        assert enforcer.check_permission(
            "ri.user.member1", "user", "read"
        ) is True

        # Write user → denied (user is not a business resource for member)
        assert enforcer.check_permission(
            "ri.user.member1", "user", "write"
        ) is False

        # Create user → denied
        assert enforcer.check_permission(
            "ri.user.member1", "user", "create"
        ) is False


class TestAdminFullAccess:
    """Admin role should have full access to all resources."""

    async def test_admin_full_access(self) -> None:
        enforcer = _make_enforcer(rbac_enabled=True)
        enforcer.sync_user_role("ri.user.admin1", "admin")

        # Read ontology
        assert enforcer.check_permission(
            "ri.user.admin1", "object_type", "read"
        ) is True

        # Write ontology
        assert enforcer.check_permission(
            "ri.user.admin1", "object_type", "write"
        ) is True

        # Manage users
        assert enforcer.check_permission(
            "ri.user.admin1", "user", "write"
        ) is True

        # Create user
        assert enforcer.check_permission(
            "ri.user.admin1", "user", "create"
        ) is True

        # Delete anything
        assert enforcer.check_permission(
            "ri.user.admin1", "tenant", "delete"
        ) is True

        # Execute actions
        assert enforcer.check_permission(
            "ri.user.admin1", "action", "execute"
        ) is True


class TestRbacDisabledAllowsAll:
    """When RBAC is disabled, all permissions should be granted."""

    async def test_rbac_disabled_allows_all(self) -> None:
        enforcer = _make_enforcer(rbac_enabled=False)

        # Even without any role assignment, viewer-like user can write
        assert enforcer.check_permission(
            "ri.user.anyone", "object_type", "write"
        ) is True

        # Can manage users
        assert enforcer.check_permission(
            "ri.user.anyone", "user", "create"
        ) is True

        # Can delete tenants
        assert enforcer.check_permission(
            "ri.user.anyone", "tenant", "delete"
        ) is True


class TestMemberCanExecuteActionsAndFunctions:
    """Member role should be able to execute actions and functions."""

    async def test_member_can_execute_actions_and_functions(self) -> None:
        enforcer = _make_enforcer(rbac_enabled=True)
        enforcer.sync_user_role("ri.user.member2", "member")

        assert enforcer.check_permission(
            "ri.user.member2", "action", "execute"
        ) is True

        assert enforcer.check_permission(
            "ri.user.member2", "function", "execute"
        ) is True


class TestViewerCannotExecute:
    """Viewer role should not be able to execute actions."""

    async def test_viewer_cannot_execute(self) -> None:
        enforcer = _make_enforcer(rbac_enabled=True)
        enforcer.sync_user_role("ri.user.viewer2", "viewer")

        assert enforcer.check_permission(
            "ri.user.viewer2", "action", "execute"
        ) is False

        assert enforcer.check_permission(
            "ri.user.viewer2", "function", "execute"
        ) is False
