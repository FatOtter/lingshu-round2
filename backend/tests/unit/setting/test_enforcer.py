"""Tests for Casbin RBAC permission enforcer."""

from lingshu.config import Settings
from lingshu.setting.authz.enforcer import PermissionEnforcer


class TestPermissionEnforcer:
    """Test the P1 RBAC enforcer (always with rbac_enabled=True)."""

    def _seeded_enforcer(self) -> PermissionEnforcer:
        """Create an enforcer with default policies seeded and RBAC enabled."""
        settings = Settings(rbac_enabled=True)
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    # ── Seed policies ────────────────────────────────────────────

    def test_seed_policies_is_idempotent(self):
        enforcer = self._seeded_enforcer()
        # Calling seed again should not raise or duplicate
        enforcer.seed_policies()

    # ── Admin role ───────────────────────────────────────────────

    def test_admin_has_full_access(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.admin1", "admin")
        assert enforcer.check_permission("ri.user.admin1", "object_type", "create") is True
        assert enforcer.check_permission("ri.user.admin1", "user", "delete") is True
        assert enforcer.check_permission("ri.user.admin1", "tenant", "write") is True
        assert enforcer.check_permission("ri.user.admin1", "anything", "any_action") is True

    # ── Member role ──────────────────────────────────────────────

    def test_member_can_read_all(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.member1", "member")
        assert enforcer.check_permission("ri.user.member1", "object_type", "read") is True
        assert enforcer.check_permission("ri.user.member1", "user", "read") is True
        assert enforcer.check_permission("ri.user.member1", "tenant", "read") is True

    def test_member_can_write_business_entities(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.member1", "member")
        for resource in [
            "object_type", "link_type", "interface_type", "action_type",
            "shared_property_type", "connection", "instance", "action",
            "function", "workflow",
        ]:
            assert enforcer.check_permission("ri.user.member1", resource, "create") is True
            assert enforcer.check_permission("ri.user.member1", resource, "update") is True
            assert enforcer.check_permission("ri.user.member1", resource, "delete") is True

    def test_member_can_execute_actions_and_functions(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.member1", "member")
        assert enforcer.check_permission("ri.user.member1", "action", "execute") is True
        assert enforcer.check_permission("ri.user.member1", "function", "execute") is True

    def test_member_cannot_write_admin_resources(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.member1", "member")
        # member cannot write to user/tenant (not in business entities)
        assert enforcer.check_permission("ri.user.member1", "user", "create") is False
        assert enforcer.check_permission("ri.user.member1", "tenant", "delete") is False

    # ── Viewer role ──────────────────────────────────────────────

    def test_viewer_can_read_all(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.viewer1", "viewer")
        assert enforcer.check_permission("ri.user.viewer1", "object_type", "read") is True
        assert enforcer.check_permission("ri.user.viewer1", "connection", "read") is True

    def test_viewer_cannot_write(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.viewer1", "viewer")
        assert enforcer.check_permission("ri.user.viewer1", "object_type", "create") is False
        assert enforcer.check_permission("ri.user.viewer1", "connection", "delete") is False
        assert enforcer.check_permission("ri.user.viewer1", "action", "execute") is False

    # ── No role (unauthenticated) ────────────────────────────────

    def test_no_role_denies_access(self):
        enforcer = self._seeded_enforcer()
        # User without any role assignment
        assert enforcer.check_permission("ri.user.nobody", "object_type", "read") is False
        assert enforcer.check_permission("ri.user.nobody", "connection", "create") is False

    # ── sync/remove user role ────────────────────────────────────

    def test_sync_user_role(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.u1", "member")
        assert enforcer.check_permission("ri.user.u1", "object_type", "read") is True

    def test_remove_user_role(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.u1", "admin")
        assert enforcer.check_permission("ri.user.u1", "anything", "any") is True

        enforcer.remove_user_role("ri.user.u1", "admin")
        assert enforcer.check_permission("ri.user.u1", "anything", "any") is False

    def test_sync_is_idempotent(self):
        enforcer = self._seeded_enforcer()
        enforcer.sync_user_role("ri.user.u1", "viewer")
        enforcer.sync_user_role("ri.user.u1", "viewer")
        assert enforcer.check_permission("ri.user.u1", "object_type", "read") is True

    def test_remove_nonexistent_role_is_safe(self):
        enforcer = self._seeded_enforcer()
        # Should not raise
        enforcer.remove_user_role("ri.user.nobody", "admin")
