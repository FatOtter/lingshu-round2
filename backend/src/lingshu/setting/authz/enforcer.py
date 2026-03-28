"""Casbin enforcer wrapper for RBAC + resource-level permission checking."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import casbin

from lingshu.infra.logging import get_logger

if TYPE_CHECKING:
    from lingshu.config import Settings

logger = get_logger("setting.authz")

# Business entity resources that members can write
_MEMBER_WRITE_RESOURCES = frozenset({
    "object_type",
    "link_type",
    "interface_type",
    "action_type",
    "shared_property_type",
    "connection",
    "instance",
    "action",
    "function",
    "workflow",
})

# Built-in system role definitions with their permissions
SYSTEM_ROLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "admin": {
        "name": "admin",
        "description": "Full access to all resources",
        "permissions": [{"resource_type": "*", "action": "*"}],
    },
    "member": {
        "name": "member",
        "description": "Read all resources, write business entities, execute actions/functions",
        "permissions": [
            {"resource_type": "*", "action": "read"},
            *[
                {"resource_type": r, "action": a}
                for r in sorted(_MEMBER_WRITE_RESOURCES)
                for a in ("write", "create", "update", "delete")
            ],
            {"resource_type": "action", "action": "execute"},
            {"resource_type": "function", "action": "execute"},
        ],
    },
    "viewer": {
        "name": "viewer",
        "description": "Read-only access to all resources",
        "permissions": [{"resource_type": "*", "action": "read"}],
    },
}


def create_enforcer() -> casbin.Enforcer:
    """Create a Casbin enforcer with the P2 RBAC + resource-level model."""
    model_path = str(Path(__file__).parent / "model.conf")
    return casbin.Enforcer(model_path)


class PermissionEnforcer:
    """Wraps Casbin enforcer for RBAC + resource-level permission checking.

    When ``rbac_enabled`` is False (default / P0 behaviour), every
    ``check_permission`` call returns True — no Casbin evaluation occurs.
    When ``rbac_enabled`` is True, Casbin RBAC rules are enforced.
    """

    def __init__(self, *, settings: Settings | None = None) -> None:
        self._enforcer = create_enforcer()
        self._rbac_enabled = settings.rbac_enabled if settings else False

    def seed_policies(self) -> None:
        """Add default role policies for admin, member, and viewer (4-tuple)."""
        e = self._enforcer

        # Admin: full access
        if not e.has_policy("admin", "*", "*", "*"):
            e.add_policy("admin", "*", "*", "*")

        # Member: read all resources
        if not e.has_policy("member", "*", "read", "*"):
            e.add_policy("member", "*", "read", "*")

        # Member: write business entities
        for resource in sorted(_MEMBER_WRITE_RESOURCES):
            for act in ("write", "create", "update", "delete"):
                if not e.has_policy("member", resource, act, "*"):
                    e.add_policy("member", resource, act, "*")

        # Member: execute actions/functions
        if not e.has_policy("member", "action", "execute", "*"):
            e.add_policy("member", "action", "execute", "*")
        if not e.has_policy("member", "function", "execute", "*"):
            e.add_policy("member", "function", "execute", "*")

        # Viewer: read all resources
        if not e.has_policy("viewer", "*", "read", "*"):
            e.add_policy("viewer", "*", "read", "*")

        logger.info("seed_policies_complete")

    def sync_user_role(self, user_rid: str, role: str) -> None:
        """Assign a role to a user: g, {user_rid}, {role}."""
        if not self._enforcer.has_grouping_policy(user_rid, role):
            self._enforcer.add_grouping_policy(user_rid, role)
            logger.info("sync_user_role", user_rid=user_rid, role=role)

    def remove_user_role(self, user_rid: str, role: str) -> None:
        """Remove a role from a user."""
        if self._enforcer.has_grouping_policy(user_rid, role):
            self._enforcer.remove_grouping_policy(user_rid, role)
            logger.info("remove_user_role", user_rid=user_rid, role=role)

    def check_permission(
        self,
        user_id: str,
        resource_type: str,
        action: str,
        resource_rid: str | None = None,
    ) -> bool:
        """Check if user has permission via RBAC + resource-level policy.

        When ``rbac_enabled`` is False, always returns True (P0 behaviour).
        Backward compatible: if resource_rid is None, uses "*" to match
        any resource-level wildcard policies.
        """
        if not self._rbac_enabled:
            return True
        res = resource_rid or "*"
        result: bool = self._enforcer.enforce(user_id, resource_type, action, res)
        return result

    def add_custom_role_policies(
        self, role_name: str, permissions: list[dict[str, Any]]
    ) -> None:
        """Add Casbin policies for a custom role based on its permission list."""
        for perm in permissions:
            resource_type = perm.get("resource_type", "*")
            action = perm.get("action", "*")
            resource_rid = perm.get("resource_rid", "*")
            if not self._enforcer.has_policy(role_name, resource_type, action, resource_rid):
                self._enforcer.add_policy(role_name, resource_type, action, resource_rid)
        logger.info("add_custom_role_policies", role=role_name, count=len(permissions))

    def remove_role_policies(self, role_name: str) -> None:
        """Remove all Casbin policies for a given role name."""
        self._enforcer.remove_filtered_policy(0, role_name)
        logger.info("remove_role_policies", role=role_name)
