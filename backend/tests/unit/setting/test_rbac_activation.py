"""Tests for RBAC activation switch (LINGSHU_RBAC_ENABLED).

T19: When rbac_enabled=False, all permission checks pass (P0 behavior).
When rbac_enabled=True, Casbin RBAC rules are actually enforced.
"""

from lingshu.config import Settings
from lingshu.setting.authz.enforcer import PermissionEnforcer


class TestRbacDisabled:
    """When RBAC is disabled (default), all requests should pass."""

    def _make_enforcer(self) -> PermissionEnforcer:
        settings = Settings(rbac_enabled=False)
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    def test_rbac_disabled_allows_all_without_role(self) -> None:
        enforcer = self._make_enforcer()
        # User with NO role assignment should still pass
        assert enforcer.check_permission("ri.user.nobody", "object_type", "create") is True
        assert enforcer.check_permission("ri.user.nobody", "user", "delete") is True
        assert enforcer.check_permission("ri.user.nobody", "tenant", "write") is True

    def test_rbac_disabled_allows_read(self) -> None:
        enforcer = self._make_enforcer()
        assert enforcer.check_permission("ri.user.any", "connection", "read") is True

    def test_rbac_disabled_allows_execute(self) -> None:
        enforcer = self._make_enforcer()
        assert enforcer.check_permission("ri.user.any", "action", "execute") is True
        assert enforcer.check_permission("ri.user.any", "function", "execute") is True


class TestRbacEnabledAdmin:
    """When RBAC is enabled, admin role should have full access."""

    def _make_enforcer(self) -> PermissionEnforcer:
        settings = Settings(rbac_enabled=True)
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    def test_admin_has_full_access(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.admin1", "admin")
        assert enforcer.check_permission("ri.user.admin1", "object_type", "create") is True
        assert enforcer.check_permission("ri.user.admin1", "user", "delete") is True
        assert enforcer.check_permission("ri.user.admin1", "tenant", "write") is True
        assert enforcer.check_permission("ri.user.admin1", "anything", "any_action") is True

    def test_admin_can_read_all(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.admin1", "admin")
        assert enforcer.check_permission("ri.user.admin1", "object_type", "read") is True
        assert enforcer.check_permission("ri.user.admin1", "user", "read") is True


class TestRbacEnabledViewer:
    """When RBAC is enabled, viewer role should only have read access."""

    def _make_enforcer(self) -> PermissionEnforcer:
        settings = Settings(rbac_enabled=True)
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    def test_viewer_can_read(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.viewer1", "viewer")
        assert enforcer.check_permission("ri.user.viewer1", "object_type", "read") is True
        assert enforcer.check_permission("ri.user.viewer1", "connection", "read") is True

    def test_viewer_cannot_write(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.viewer1", "viewer")
        assert enforcer.check_permission("ri.user.viewer1", "object_type", "create") is False
        assert enforcer.check_permission("ri.user.viewer1", "connection", "delete") is False
        assert enforcer.check_permission("ri.user.viewer1", "action", "execute") is False

    def test_viewer_cannot_write_admin_resources(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.viewer1", "viewer")
        assert enforcer.check_permission("ri.user.viewer1", "user", "create") is False
        assert enforcer.check_permission("ri.user.viewer1", "tenant", "delete") is False


class TestRbacEnabledMember:
    """When RBAC is enabled, member role should have appropriate permissions."""

    def _make_enforcer(self) -> PermissionEnforcer:
        settings = Settings(rbac_enabled=True)
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    def test_member_can_read_all(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.member1", "member")
        assert enforcer.check_permission("ri.user.member1", "object_type", "read") is True
        assert enforcer.check_permission("ri.user.member1", "user", "read") is True

    def test_member_can_write_business_entities(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.member1", "member")
        for resource in [
            "object_type", "link_type", "interface_type", "action_type",
            "shared_property_type", "connection", "instance", "action",
            "function", "workflow",
        ]:
            assert enforcer.check_permission("ri.user.member1", resource, "create") is True
            assert enforcer.check_permission("ri.user.member1", resource, "update") is True
            assert enforcer.check_permission("ri.user.member1", resource, "delete") is True

    def test_member_can_execute(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.member1", "member")
        assert enforcer.check_permission("ri.user.member1", "action", "execute") is True
        assert enforcer.check_permission("ri.user.member1", "function", "execute") is True

    def test_member_cannot_write_admin_resources(self) -> None:
        enforcer = self._make_enforcer()
        enforcer.sync_user_role("ri.user.member1", "member")
        assert enforcer.check_permission("ri.user.member1", "user", "create") is False
        assert enforcer.check_permission("ri.user.member1", "tenant", "delete") is False


class TestRbacEnabledNoRole:
    """When RBAC is enabled, users without roles should be denied."""

    def _make_enforcer(self) -> PermissionEnforcer:
        settings = Settings(rbac_enabled=True)
        enforcer = PermissionEnforcer(settings=settings)
        enforcer.seed_policies()
        return enforcer

    def test_no_role_denies_all(self) -> None:
        enforcer = self._make_enforcer()
        assert enforcer.check_permission("ri.user.nobody", "object_type", "read") is False
        assert enforcer.check_permission("ri.user.nobody", "connection", "create") is False


class TestRbacConfigDefault:
    """Test that rbac_enabled defaults to False in Settings."""

    def test_default_is_false(self) -> None:
        settings = Settings()
        assert settings.rbac_enabled is False
