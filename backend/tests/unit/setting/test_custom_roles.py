"""Tests for Phase 9.5: Custom Roles + Resource-Level Permissions."""

import pytest

from lingshu.config import Settings
from lingshu.setting.authz.enforcer import PermissionEnforcer


class TestP2ResourceLevelPermissions:
    """Test the P2 RBAC + resource-level enforcer."""

    def _seeded_enforcer(self) -> PermissionEnforcer:
        settings = Settings(rbac_enabled=True)
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    # ── Backward compatibility (P1 style, resource_rid=None) ─────

    def test_admin_full_access_without_resource_rid(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.admin1", "admin")
        assert enforcer.check_permission("ri.user.admin1", "object_type", "create") is True
        assert enforcer.check_permission("ri.user.admin1", "user", "delete") is True

    def test_member_read_all_without_resource_rid(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.m1", "member")
        assert enforcer.check_permission("ri.user.m1", "object_type", "read") is True
        assert enforcer.check_permission("ri.user.m1", "tenant", "read") is True

    def test_member_write_business_entities_without_resource_rid(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.m1", "member")
        assert enforcer.check_permission("ri.user.m1", "object_type", "create") is True
        assert enforcer.check_permission("ri.user.m1", "connection", "delete") is True

    def test_member_cannot_write_admin_resources_without_resource_rid(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.m1", "member")
        assert enforcer.check_permission("ri.user.m1", "user", "create") is False
        assert enforcer.check_permission("ri.user.m1", "tenant", "delete") is False

    def test_viewer_read_only_without_resource_rid(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.v1", "viewer")
        assert enforcer.check_permission("ri.user.v1", "object_type", "read") is True
        assert enforcer.check_permission("ri.user.v1", "object_type", "create") is False

    def test_no_role_denies_access(self):
        enforcer = self._seeded_enforcer()
        assert enforcer.check_permission("ri.user.nobody", "object_type", "read") is False

    # ── Resource-level permissions (P2, resource_rid specified) ───

    def test_admin_access_with_specific_resource_rid(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.admin1", "admin")
        assert enforcer.check_permission(
            "ri.user.admin1", "object_type", "read", "ri.obj.specific-123"
        ) is True

    def test_member_access_with_specific_resource_rid(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.m1", "member")
        # Wildcard policies match any resource_rid
        assert enforcer.check_permission(
            "ri.user.m1", "object_type", "read", "ri.obj.specific-123"
        ) is True

    def test_viewer_access_with_specific_resource_rid(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.v1", "viewer")
        assert enforcer.check_permission(
            "ri.user.v1", "connection", "read", "ri.conn.abc"
        ) is True
        assert enforcer.check_permission(
            "ri.user.v1", "connection", "create", "ri.conn.abc"
        ) is False

    # ── Custom role with resource-level permissions ───────────────

    def test_custom_role_resource_level_permission(self):
        enforcer = self._seeded_enforcer()
        # Create a custom role that can only read one specific resource
        enforcer.add_custom_role_policies("data_analyst", [
            {"resource_type": "connection", "action": "read", "resource_rid": "ri.conn.sales-db"},
        ])
        enforcer.sync_user_role("ri.user.analyst1", "data_analyst")

        # Can read the specific resource
        assert enforcer.check_permission(
            "ri.user.analyst1", "connection", "read", "ri.conn.sales-db"
        ) is True

        # Cannot read a different resource
        assert enforcer.check_permission(
            "ri.user.analyst1", "connection", "read", "ri.conn.other-db"
        ) is False

        # Cannot write even the allowed resource
        assert enforcer.check_permission(
            "ri.user.analyst1", "connection", "create", "ri.conn.sales-db"
        ) is False

    def test_custom_role_wildcard_resource(self):
        enforcer = self._seeded_enforcer()
        enforcer.add_custom_role_policies("editor", [
            {"resource_type": "object_type", "action": "read"},
            {"resource_type": "object_type", "action": "update"},
        ])
        enforcer.sync_user_role("ri.user.editor1", "editor")

        # Wildcard resource_rid (default) matches any
        assert enforcer.check_permission(
            "ri.user.editor1", "object_type", "read", "ri.obj.any"
        ) is True
        assert enforcer.check_permission(
            "ri.user.editor1", "object_type", "update"
        ) is True
        assert enforcer.check_permission(
            "ri.user.editor1", "object_type", "delete"
        ) is False

    def test_custom_role_multiple_permissions(self):
        enforcer = self._seeded_enforcer()
        enforcer.add_custom_role_policies("project_lead", [
            {"resource_type": "workflow", "action": "read"},
            {"resource_type": "workflow", "action": "create"},
            {"resource_type": "workflow", "action": "update"},
            {"resource_type": "function", "action": "execute"},
        ])
        enforcer.sync_user_role("ri.user.lead1", "project_lead")

        assert enforcer.check_permission("ri.user.lead1", "workflow", "read") is True
        assert enforcer.check_permission("ri.user.lead1", "workflow", "create") is True
        assert enforcer.check_permission("ri.user.lead1", "workflow", "delete") is False
        assert enforcer.check_permission("ri.user.lead1", "function", "execute") is True

    # ── Remove custom role policies ──────────────────────────────

    def test_remove_role_policies(self):
        enforcer = self._seeded_enforcer()
        enforcer.add_custom_role_policies("temp_role", [
            {"resource_type": "object_type", "action": "read"},
        ])
        enforcer.sync_user_role("ri.user.temp1", "temp_role")
        assert enforcer.check_permission("ri.user.temp1", "object_type", "read") is True

        # Remove role policies
        enforcer.remove_role_policies("temp_role")
        # After removing policies, the user's grouping still exists but
        # no matching policy, so permission denied
        assert enforcer.check_permission("ri.user.temp1", "object_type", "read") is False

    def test_remove_role_policies_does_not_affect_other_roles(self):
        enforcer = self._seeded_enforcer()
        enforcer.add_custom_role_policies("role_a", [
            {"resource_type": "connection", "action": "read"},
        ])
        enforcer.sync_user_role("ri.user.a1", "role_a")
        enforcer.sync_user_role("ri.user.m1", "member")

        # Remove role_a policies
        enforcer.remove_role_policies("role_a")

        # member should still work
        assert enforcer.check_permission("ri.user.m1", "connection", "read") is True

    # ── sync/remove user role (still works with P2) ──────────────

    def test_sync_and_remove_user_role_p2(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.u1", "admin")
        assert enforcer.check_permission("ri.user.u1", "anything", "any") is True

        enforcer.remove_user_role("ri.user.u1", "admin")
        assert enforcer.check_permission("ri.user.u1", "anything", "any") is False

    def test_seed_policies_idempotent_p2(self):
        enforcer = self._seeded_enforcer()
        enforcer.seed_policies()  # Second call should be safe
        enforcer.sync_user_role("ri.user.admin1", "admin")
        assert enforcer.check_permission("ri.user.admin1", "object_type", "create") is True

    # ── System role protection (tested at enforcer level) ────────

    def test_system_role_policies_cannot_be_removed_accidentally(self):
        """Verify that removing system role policies can be done (for re-sync)."""
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.admin1", "admin")

        # This is allowed at the enforcer level (service layer protects system roles)
        enforcer.remove_role_policies("admin")
        assert enforcer.check_permission("ri.user.admin1", "object_type", "create") is False

        # Re-seed restores them
        enforcer.seed_policies()
        assert enforcer.check_permission("ri.user.admin1", "object_type", "create") is True
