"""RID (Resource Identifier) generation and validation.

Format: ri.{resource_type}.{uuid}
"""

import re
import uuid

RID_PATTERN = re.compile(
    r"^ri\.[a-z]+\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

VALID_RESOURCE_TYPES = frozenset({
    "obj",
    "link",
    "iface",
    "action",
    "shprop",
    "prop",
    "snap",
    "conn",
    "func",
    "workflow",
    "session",
    "model",
    "skill",
    "mcp",
    "subagent",
    "user",
    "tenant",
    "role",
})


def generate_rid(resource_type: str) -> str:
    """Generate a new RID for the given resource type.

    Args:
        resource_type: One of the registered resource types (e.g., 'obj', 'user').

    Returns:
        A new RID string like 'ri.obj.550e8400-e29b-41d4-a716-446655440000'.

    Raises:
        ValueError: If resource_type is not registered.
    """
    if resource_type not in VALID_RESOURCE_TYPES:
        raise ValueError(
            f"Unknown resource type: {resource_type}. "
            f"Valid types: {sorted(VALID_RESOURCE_TYPES)}"
        )
    return f"ri.{resource_type}.{uuid.uuid4()}"


def validate_rid(rid: str) -> bool:
    """Check if a string is a valid RID format."""
    return bool(RID_PATTERN.match(rid))


def parse_rid(rid: str) -> tuple[str, str]:
    """Parse a RID into (resource_type, uuid).

    Raises:
        ValueError: If the RID format is invalid.
    """
    if not validate_rid(rid):
        raise ValueError(f"Invalid RID format: {rid}")
    parts = rid.split(".", 2)
    return parts[1], parts[2]


def validate_rid_type(rid: str, expected_type: str) -> bool:
    """Validate that a RID matches the expected resource type."""
    if not validate_rid(rid):
        return False
    resource_type, _ = parse_rid(rid)
    return resource_type == expected_type
