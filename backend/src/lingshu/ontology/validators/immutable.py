"""Immutable field protection: prevent modification of identity fields after creation."""

from typing import Any

from lingshu.infra.errors import AppError, ErrorCode

# Fields that cannot be changed after entity creation
IMMUTABLE_FIELDS: frozenset[str] = frozenset({
    "rid",
    "api_name",
    "tenant_id",
    "created_at",
})

# Entity-specific immutable fields
ENTITY_IMMUTABLE_FIELDS: dict[str, frozenset[str]] = {
    "LinkType": frozenset({"source_object_type_rid", "target_object_type_rid"}),
    "InterfaceType": frozenset({"category"}),
    "SharedPropertyType": frozenset({"data_type"}),
}


def check_immutable_fields(
    label: str,
    updates: dict[str, Any],
) -> None:
    """Raise AppError if updates contain any immutable fields.

    Args:
        label: The entity type label (e.g. "ObjectType").
        updates: The update dict to validate.

    Raises:
        AppError: If any immutable field is being modified.
    """
    all_immutable = IMMUTABLE_FIELDS | ENTITY_IMMUTABLE_FIELDS.get(label, frozenset())
    violated = [f for f in updates if f in all_immutable]
    if violated:
        raise AppError(
            code=ErrorCode.ONTOLOGY_IMMUTABLE_FIELD,
            message=f"Cannot modify immutable field(s): {', '.join(sorted(violated))}",
            details={"fields": sorted(violated), "entity_type": label},
        )
