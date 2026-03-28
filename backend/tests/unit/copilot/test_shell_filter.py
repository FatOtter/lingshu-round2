"""Unit tests for shell mode capability filtering."""

import pytest

from lingshu.copilot.agent.tools import (
    SHELL_MODULE_CAPABILITIES,
    filter_capabilities_for_shell,
)
from lingshu.function.schemas.responses import CapabilityDescriptor


def _make_cap(
    *,
    cap_type: str = "function",
    safety_level: str = "SAFETY_READ_ONLY",
    api_name: str = "test_cap",
) -> CapabilityDescriptor:
    """Helper to build a CapabilityDescriptor for testing."""
    return CapabilityDescriptor(
        type=cap_type,
        rid=f"ri.{cap_type}.1",
        api_name=api_name,
        display_name=api_name.replace("_", " ").title(),
        safety_level=safety_level,
    )


class TestShellModuleCapabilities:
    """Verify the module-to-capability mapping is correct."""

    def test_ontology_allows_function_only(self) -> None:
        assert SHELL_MODULE_CAPABILITIES["ontology"] == {"function"}

    def test_data_allows_function_and_action(self) -> None:
        assert SHELL_MODULE_CAPABILITIES["data"] == {"function", "action"}

    def test_function_allows_function_and_action(self) -> None:
        assert SHELL_MODULE_CAPABILITIES["function"] == {"function", "action"}

    def test_setting_allows_function_only(self) -> None:
        assert SHELL_MODULE_CAPABILITIES["setting"] == {"function"}


class TestFilterCapabilitiesForShell:
    """Test filter_capabilities_for_shell behavior."""

    def test_ontology_only_read_only_functions(self) -> None:
        caps = [
            _make_cap(cap_type="function", safety_level="SAFETY_READ_ONLY", api_name="read_schema"),
            _make_cap(cap_type="function", safety_level="SAFETY_WRITE", api_name="write_schema"),
            _make_cap(cap_type="action", safety_level="SAFETY_READ_ONLY", api_name="some_action"),
        ]
        result = filter_capabilities_for_shell(caps, "ontology")
        assert len(result) == 1
        assert result[0].api_name == "read_schema"

    def test_data_allows_functions_and_actions(self) -> None:
        caps = [
            _make_cap(cap_type="function", api_name="query_data"),
            _make_cap(cap_type="action", api_name="create_record"),
            _make_cap(cap_type="function", safety_level="SAFETY_WRITE", api_name="write_func"),
        ]
        result = filter_capabilities_for_shell(caps, "data")
        assert len(result) == 3

    def test_data_excludes_unknown_types(self) -> None:
        caps = [
            _make_cap(cap_type="function", api_name="query_data"),
            _make_cap(cap_type="workflow", api_name="run_workflow"),
        ]
        result = filter_capabilities_for_shell(caps, "data")
        assert len(result) == 1
        assert result[0].api_name == "query_data"

    def test_setting_only_functions(self) -> None:
        caps = [
            _make_cap(cap_type="function", api_name="get_config"),
            _make_cap(cap_type="action", api_name="update_config"),
        ]
        result = filter_capabilities_for_shell(caps, "setting")
        assert len(result) == 1
        assert result[0].api_name == "get_config"

    def test_unknown_module_returns_empty(self) -> None:
        caps = [
            _make_cap(cap_type="function", api_name="something"),
            _make_cap(cap_type="action", api_name="another"),
        ]
        result = filter_capabilities_for_shell(caps, "unknown_module")
        assert len(result) == 0

    def test_empty_capabilities_returns_empty(self) -> None:
        result = filter_capabilities_for_shell([], "data")
        assert result == []

    def test_function_module_allows_all_capability_types(self) -> None:
        caps = [
            _make_cap(cap_type="function", api_name="func1"),
            _make_cap(cap_type="action", api_name="action1"),
        ]
        result = filter_capabilities_for_shell(caps, "function")
        assert len(result) == 2

    def test_does_not_mutate_input(self) -> None:
        caps = [
            _make_cap(cap_type="function", api_name="func1"),
            _make_cap(cap_type="action", api_name="action1"),
        ]
        original_len = len(caps)
        filter_capabilities_for_shell(caps, "ontology")
        assert len(caps) == original_len


class TestAgentModeNoFiltering:
    """Verify that agent mode (no filter call) keeps all capabilities."""

    def test_all_capabilities_available_when_not_filtered(self) -> None:
        """Agent mode simply doesn't call filter_capabilities_for_shell."""
        caps = [
            _make_cap(cap_type="function", api_name="func1"),
            _make_cap(cap_type="action", api_name="action1"),
            _make_cap(cap_type="function", safety_level="SAFETY_WRITE", api_name="write_func"),
        ]
        # In agent mode, no filtering is applied - caps stay as-is
        assert len(caps) == 3
