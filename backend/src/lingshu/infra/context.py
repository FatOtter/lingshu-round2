"""Request context using ContextVar for tenant isolation."""

from contextvars import ContextVar

user_id_var: ContextVar[str] = ContextVar("user_id")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id")
role_var: ContextVar[str] = ContextVar("role")
request_id_var: ContextVar[str] = ContextVar("request_id")


def get_user_id() -> str:
    """Return current request's user_id."""
    try:
        return user_id_var.get()
    except LookupError:
        raise RuntimeError("user_id not set in request context") from None


def get_tenant_id() -> str:
    """Return current request's tenant_id."""
    try:
        return tenant_id_var.get()
    except LookupError:
        raise RuntimeError("tenant_id not set in request context") from None


def get_role() -> str:
    """Return current request's role."""
    try:
        return role_var.get()
    except LookupError:
        raise RuntimeError("role not set in request context") from None


def get_request_id() -> str:
    """Return current request's request_id."""
    try:
        return request_id_var.get()
    except LookupError:
        return "unknown"
