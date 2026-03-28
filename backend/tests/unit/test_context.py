"""Tests for request context ContextVar utilities."""

import pytest

from lingshu.infra.context import (
    get_request_id,
    get_role,
    get_tenant_id,
    get_user_id,
    request_id_var,
    role_var,
    tenant_id_var,
    user_id_var,
)


class TestContextVars:
    def test_get_user_id_when_set(self):
        token = user_id_var.set("ri.user.test-123")
        try:
            assert get_user_id() == "ri.user.test-123"
        finally:
            user_id_var.reset(token)

    def test_get_user_id_raises_when_not_set(self):
        with pytest.raises(RuntimeError, match="user_id not set"):
            get_user_id()

    def test_get_tenant_id_when_set(self):
        token = tenant_id_var.set("ri.tenant.test-456")
        try:
            assert get_tenant_id() == "ri.tenant.test-456"
        finally:
            tenant_id_var.reset(token)

    def test_get_tenant_id_raises_when_not_set(self):
        with pytest.raises(RuntimeError, match="tenant_id not set"):
            get_tenant_id()

    def test_get_role_when_set(self):
        token = role_var.set("admin")
        try:
            assert get_role() == "admin"
        finally:
            role_var.reset(token)

    def test_get_role_raises_when_not_set(self):
        with pytest.raises(RuntimeError, match="role not set"):
            get_role()

    def test_get_request_id_returns_unknown_when_not_set(self):
        assert get_request_id() == "unknown"

    def test_get_request_id_when_set(self):
        token = request_id_var.set("req_abc123")
        try:
            assert get_request_id() == "req_abc123"
        finally:
            request_id_var.reset(token)
