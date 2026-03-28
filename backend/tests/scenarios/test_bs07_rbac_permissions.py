"""BS-07: RBAC Permission Enforcement.

Scenario: Verify role-based access control for admin, member, and viewer roles.

Steps:
1. RBAC enabled
2. Admin can do everything
3. Member can create but not manage users
4. Viewer can read but not write
5. RBAC disabled -> all allowed
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from lingshu.setting.authz.enforcer import PermissionEnforcer


class TestRBACPermissions:
    """RBAC permission enforcement scenario."""

    @pytest.fixture
    def enforcer_enabled(self) -> PermissionEnforcer:
        """Create an enforcer with RBAC enabled."""
        settings = MagicMock()
        settings.rbac_enabled = True
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    @pytest.fixture
    def enforcer_disabled(self) -> PermissionEnforcer:
        """Create an enforcer with RBAC disabled."""
        settings = MagicMock()
        settings.rbac_enabled = False
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    # ── Step 2: Admin can do everything ──

    def test_admin_can_read_all(self, enforcer_enabled) -> None:
        """Admin can read any resource type."""
        enforcer_enabled.sync_user_role("ri.user.admin", "admin")
        assert enforcer_enabled.check_permission("ri.user.admin", "object_type", "read")
        assert enforcer_enabled.check_permission("ri.user.admin", "user", "read")
        assert enforcer_enabled.check_permission("ri.user.admin", "tenant", "read")

    def test_admin_can_write_all(self, enforcer_enabled) -> None:
        """Admin can write any resource type."""
        enforcer_enabled.sync_user_role("ri.user.admin", "admin")
        assert enforcer_enabled.check_permission("ri.user.admin", "object_type", "write")
        assert enforcer_enabled.check_permission("ri.user.admin", "user", "write")
        assert enforcer_enabled.check_permission("ri.user.admin", "tenant", "write")

    def test_admin_can_manage_users(self, enforcer_enabled) -> None:
        """Admin can create/update/delete users."""
        enforcer_enabled.sync_user_role("ri.user.admin", "admin")
        assert enforcer_enabled.check_permission("ri.user.admin", "user", "create")
        assert enforcer_enabled.check_permission("ri.user.admin", "user", "update")
        assert enforcer_enabled.check_permission("ri.user.admin", "user", "delete")

    # ── Step 3: Member can create ontology but not manage users ──

    def test_member_can_read_all(self, enforcer_enabled) -> None:
        """Member can read any resource type."""
        enforcer_enabled.sync_user_role("ri.user.member", "member")
        assert enforcer_enabled.check_permission("ri.user.member", "object_type", "read")
        assert enforcer_enabled.check_permission("ri.user.member", "connection", "read")
        assert enforcer_enabled.check_permission("ri.user.member", "user", "read")

    def test_member_can_create_ontology_entities(self, enforcer_enabled) -> None:
        """Member can create business entities."""
        enforcer_enabled.sync_user_role("ri.user.member", "member")
        assert enforcer_enabled.check_permission("ri.user.member", "object_type", "create")
        assert enforcer_enabled.check_permission("ri.user.member", "link_type", "create")
        assert enforcer_enabled.check_permission("ri.user.member", "action_type", "write")

    def test_member_can_execute_actions(self, enforcer_enabled) -> None:
        """Member can execute actions and functions."""
        enforcer_enabled.sync_user_role("ri.user.member", "member")
        assert enforcer_enabled.check_permission("ri.user.member", "action", "execute")
        assert enforcer_enabled.check_permission("ri.user.member", "function", "execute")

    def test_member_cannot_manage_users(self, enforcer_enabled) -> None:
        """Member cannot create/update/delete users."""
        enforcer_enabled.sync_user_role("ri.user.member", "member")
        assert not enforcer_enabled.check_permission("ri.user.member", "user", "create")
        assert not enforcer_enabled.check_permission("ri.user.member", "user", "delete")

    def test_member_cannot_manage_tenants(self, enforcer_enabled) -> None:
        """Member cannot manage tenants."""
        enforcer_enabled.sync_user_role("ri.user.member", "member")
        assert not enforcer_enabled.check_permission("ri.user.member", "tenant", "create")
        assert not enforcer_enabled.check_permission("ri.user.member", "tenant", "delete")

    # ── Step 4: Viewer can only read ──

    def test_viewer_can_read_all(self, enforcer_enabled) -> None:
        """Viewer can read any resource type."""
        enforcer_enabled.sync_user_role("ri.user.viewer", "viewer")
        assert enforcer_enabled.check_permission("ri.user.viewer", "object_type", "read")
        assert enforcer_enabled.check_permission("ri.user.viewer", "connection", "read")

    def test_viewer_cannot_write(self, enforcer_enabled) -> None:
        """Viewer cannot write any resource."""
        enforcer_enabled.sync_user_role("ri.user.viewer", "viewer")
        assert not enforcer_enabled.check_permission("ri.user.viewer", "object_type", "write")
        assert not enforcer_enabled.check_permission("ri.user.viewer", "object_type", "create")
        assert not enforcer_enabled.check_permission("ri.user.viewer", "object_type", "delete")

    def test_viewer_cannot_execute(self, enforcer_enabled) -> None:
        """Viewer cannot execute actions or functions."""
        enforcer_enabled.sync_user_role("ri.user.viewer", "viewer")
        assert not enforcer_enabled.check_permission("ri.user.viewer", "action", "execute")
        assert not enforcer_enabled.check_permission("ri.user.viewer", "function", "execute")

    def test_viewer_cannot_manage_users(self, enforcer_enabled) -> None:
        """Viewer cannot manage users."""
        enforcer_enabled.sync_user_role("ri.user.viewer", "viewer")
        assert not enforcer_enabled.check_permission("ri.user.viewer", "user", "create")
        assert not enforcer_enabled.check_permission("ri.user.viewer", "user", "update")

    # ── Step 5: RBAC disabled -> all allowed ──

    def test_rbac_disabled_viewer_can_write(self, enforcer_disabled) -> None:
        """With RBAC disabled, viewer can write."""
        enforcer_disabled.sync_user_role("ri.user.viewer", "viewer")
        assert enforcer_disabled.check_permission("ri.user.viewer", "object_type", "write")

    def test_rbac_disabled_viewer_can_manage_users(
        self, enforcer_disabled,
    ) -> None:
        """With RBAC disabled, viewer can manage users."""
        enforcer_disabled.sync_user_role("ri.user.viewer", "viewer")
        assert enforcer_disabled.check_permission("ri.user.viewer", "user", "create")
        assert enforcer_disabled.check_permission("ri.user.viewer", "user", "delete")

    def test_rbac_disabled_all_operations_allowed(
        self, enforcer_disabled,
    ) -> None:
        """With RBAC disabled, all operations are allowed for any user."""
        assert enforcer_disabled.check_permission("ri.user.unknown", "anything", "delete")

    # ── No role assigned ──

    def test_no_role_user_denied(self, enforcer_enabled) -> None:
        """User with no role cannot do anything (RBAC enabled)."""
        # Do NOT sync any role for this user
        assert not enforcer_enabled.check_permission("ri.user.norole", "object_type", "read")
        assert not enforcer_enabled.check_permission("ri.user.norole", "object_type", "write")

    # ── Resource-level permission ──

    def test_resource_level_permission(self, enforcer_enabled) -> None:
        """Check permission with specific resource RID."""
        enforcer_enabled.sync_user_role("ri.user.admin", "admin")
        assert enforcer_enabled.check_permission(
            "ri.user.admin", "object_type", "read", "ri.obj.specific",
        )
