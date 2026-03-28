"""SettingService Protocol: interface for other modules to call."""

from typing import Any, Protocol


class SettingService(Protocol):
    """Protocol interface exposed to other capability domains."""

    def get_current_user_id(self) -> str:
        """Get current user's RID from request context."""
        ...

    def get_current_tenant_id(self) -> str:
        """Get current tenant's RID from request context."""
        ...

    def check_permission(
        self,
        user_id: str,
        resource_type: str,
        action: str,
        resource_rid: str | None = None,
    ) -> bool:
        """Check if user has permission. P0: always True."""
        ...

    async def write_audit_log(
        self,
        module: str,
        event_type: str,
        action: str,
        resource_type: str | None = None,
        resource_rid: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Write an audit log entry. Auto-injects tenant_id, user_id, request_id from context."""
        ...
