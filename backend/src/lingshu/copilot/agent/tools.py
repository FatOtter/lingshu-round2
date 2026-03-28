"""Tool binding: convert FunctionService capabilities to LangGraph tools."""

from typing import Any

from lingshu.function.interface import FunctionService
from lingshu.function.schemas.responses import CapabilityDescriptor

# Module to capability type mapping for shell mode
SHELL_MODULE_CAPABILITIES: dict[str, set[str]] = {
    "ontology": {"function"},  # Schema queries only - read operations
    "data": {"function", "action"},  # Instance queries + browsing + actions
    "function": {"function", "action"},  # All capabilities
    "setting": {"function"},  # System config queries
}


def filter_capabilities_for_shell(
    capabilities: list[CapabilityDescriptor],
    module: str,
) -> list[CapabilityDescriptor]:
    """Filter capabilities to only those relevant for the given module in shell mode.

    In shell mode, tools are scoped to the current module context.
    In agent mode, all tools are available (no filtering).
    """
    allowed_types = SHELL_MODULE_CAPABILITIES.get(module, set())

    # Additional filtering: for ontology module, only read-only capabilities
    if module == "ontology":
        return [
            cap for cap in capabilities
            if cap.type in allowed_types and cap.safety_level == "SAFETY_READ_ONLY"
        ]

    return [cap for cap in capabilities if cap.type in allowed_types]


def make_tool_schema(cap: CapabilityDescriptor) -> dict[str, Any]:
    """Convert a CapabilityDescriptor into a tool schema for LLM binding.

    Returns a dict describing the tool for the LLM to understand.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param in cap.parameters:
        param_name = param.get("api_name", "")
        param_schema: dict[str, Any] = {
            "type": "string",
            "description": param.get("display_name", param_name),
        }
        data_type = param.get("data_type", "DT_STRING")
        if data_type == "DT_INTEGER":
            param_schema["type"] = "integer"
        elif data_type == "DT_BOOLEAN":
            param_schema["type"] = "boolean"
        elif data_type == "DT_DOUBLE":
            param_schema["type"] = "number"

        properties[param_name] = param_schema
        if param.get("required", False):
            required.append(param_name)

    return {
        "name": cap.api_name,
        "description": cap.description or cap.display_name,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        "metadata": {
            "type": cap.type,
            "rid": cap.rid,
            "safety_level": cap.safety_level,
        },
    }


def build_tool_schemas(
    capabilities: list[CapabilityDescriptor],
) -> list[dict[str, Any]]:
    """Build tool schemas from a list of capabilities."""
    return [make_tool_schema(cap) for cap in capabilities]


async def execute_tool_call(
    function_service: FunctionService,
    tool_name: str,
    tool_args: dict[str, Any],
    capabilities: list[CapabilityDescriptor],
    *,
    branch: str | None = None,
) -> dict[str, Any]:
    """Execute a tool call by routing to the appropriate FunctionService method."""
    cap = next((c for c in capabilities if c.api_name == tool_name), None)
    if cap is None:
        return {"error": f"Unknown tool: {tool_name}"}

    if cap.type == "action":
        result = await function_service.execute_action(
            cap.rid, tool_args,
            branch=branch, skip_confirmation=True,
        )
        return result
    if cap.type == "function":
        result = await function_service.execute_function(
            cap.rid, tool_args,
            branch=branch,
        )
        return result

    return {"error": f"Unsupported capability type: {cap.type}"}
