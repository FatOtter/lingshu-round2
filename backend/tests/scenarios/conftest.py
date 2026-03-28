"""Shared fixtures for business scenario tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from contextvars import Token

from lingshu.infra.context import tenant_id_var, user_id_var


@pytest.fixture(autouse=True)
def set_context():
    """Set tenant and user context vars for all scenario tests."""
    t1: Token[str] = tenant_id_var.set("t1")
    t2: Token[str] = user_id_var.set("u1")
    yield
    tenant_id_var.reset(t1)
    user_id_var.reset(t2)


@pytest.fixture
def tenant_id() -> str:
    """Default tenant ID for scenario tests."""
    return "t1"


@pytest.fixture
def admin_user_id() -> str:
    """Default admin user ID for scenario tests."""
    return "u1"


@pytest.fixture
def tenant_id_b() -> str:
    """Second tenant ID for multi-tenant scenario tests."""
    return "t2"


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock SQLAlchemy async session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


def make_mock_result(value: Any) -> MagicMock:
    """Create a mock query result wrapping scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    result.scalar_one = MagicMock(return_value=0)
    return result


# ---------------------------------------------------------------------------
# Graph node factory helpers
# ---------------------------------------------------------------------------

def _base_node(
    rid: str,
    api_name: str,
    *,
    label: str = "ObjectType",
    tenant_id: str = "t1",
    display_name: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Base factory for graph node dicts."""
    node: dict[str, Any] = {
        "rid": rid,
        "api_name": api_name,
        "display_name": display_name or api_name.replace("_", " ").title(),
        "tenant_id": tenant_id,
        "label": label,
        "is_draft": True,
        "is_staging": False,
        "is_active": False,
        "description": "",
        "properties": [],
    }
    node.update(extra)
    return node


def make_object_type_node(
    rid: str,
    api_name: str,
    *,
    display_name: str | None = None,
    tenant_id: str = "t1",
    implements_interface_type_rids: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    node = _base_node(
        rid, api_name,
        label="ObjectType",
        tenant_id=tenant_id,
        display_name=display_name,
        **extra,
    )
    node["implements_interface_type_rids"] = implements_interface_type_rids or []
    return node


def make_link_type_node(
    rid: str,
    api_name: str,
    *,
    display_name: str | None = None,
    tenant_id: str = "t1",
    source_object_type_rid: str = "",
    target_object_type_rid: str = "",
    **extra: Any,
) -> dict[str, Any]:
    node = _base_node(
        rid, api_name,
        label="LinkType",
        tenant_id=tenant_id,
        display_name=display_name,
        **extra,
    )
    node["source_object_type_rid"] = source_object_type_rid
    node["target_object_type_rid"] = target_object_type_rid
    return node


def make_interface_type_node(
    rid: str,
    api_name: str,
    *,
    display_name: str | None = None,
    tenant_id: str = "t1",
    **extra: Any,
) -> dict[str, Any]:
    return _base_node(
        rid, api_name,
        label="InterfaceType",
        tenant_id=tenant_id,
        display_name=display_name,
        **extra,
    )


def make_action_type_node(
    rid: str,
    api_name: str,
    *,
    display_name: str | None = None,
    tenant_id: str = "t1",
    **extra: Any,
) -> dict[str, Any]:
    return _base_node(
        rid, api_name,
        label="ActionType",
        tenant_id=tenant_id,
        display_name=display_name,
        **extra,
    )


def make_shared_property_type_node(
    rid: str,
    api_name: str,
    *,
    display_name: str | None = None,
    tenant_id: str = "t1",
    **extra: Any,
) -> dict[str, Any]:
    return _base_node(
        rid, api_name,
        label="SharedPropertyType",
        tenant_id=tenant_id,
        display_name=display_name,
        **extra,
    )


def make_property_type_node(
    rid: str,
    api_name: str,
    *,
    display_name: str | None = None,
    tenant_id: str = "t1",
    base_type: str = "string",
    **extra: Any,
) -> dict[str, Any]:
    node = _base_node(
        rid, api_name,
        label="PropertyType",
        tenant_id=tenant_id,
        display_name=display_name,
        **extra,
    )
    node["base_type"] = base_type
    return node


def make_staging_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *node* with staging flags set.

    Note: commit_staging logic checks ``is_active`` on staging nodes to
    decide create/update vs delete.  Nodes intended for promotion must
    have ``is_active=True`` so the commit path treats them as creates.
    """
    result = {**node}
    result["is_draft"] = False
    result["is_staging"] = True
    result["is_active"] = True
    return result


def make_active_node(node: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Return a copy of *node* with active flags set."""
    result = {**node}
    result["is_draft"] = False
    result["is_staging"] = False
    result["is_active"] = True
    result.update(overrides)
    return result


def mock_session() -> AsyncMock:
    """Create a mock async DB session (callable version, not fixture)."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session
