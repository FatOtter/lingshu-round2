"""Cascade update logic: SharedPropertyType -> PropertyType propagation."""

from typing import Any

from lingshu.ontology.repository.graph_repo import GraphRepository

# Fields that cascade from SharedPropertyType to PropertyType (unless overridden)
CASCADE_FIELDS = frozenset({
    "display_name",
    "description",
    "widget",
    "validation",
    "compliance",
})


async def cascade_shared_property_update(
    graph_repo: GraphRepository,
    shared_rid: str,
    tenant_id: str,
    updated_fields: dict[str, Any],
    old_values: dict[str, Any] | None = None,
) -> list[str]:
    """Cascade changes from SharedPropertyType to inheriting PropertyTypes.

    Uses value comparison to detect overrides: if the PropertyType's current value
    matches the old SharedPropertyType value, it has not been locally overridden
    and should receive the cascade update.

    Args:
        graph_repo: The graph repository.
        shared_rid: RID of the SharedPropertyType being updated.
        tenant_id: Tenant identifier.
        updated_fields: Dict of field name -> new value being set.
        old_values: Dict of field name -> old value from before the update.
            When provided, override detection uses value comparison.
            When None, falls back to always cascading (legacy behavior).

    Returns:
        List of affected PropertyType RIDs.
    """
    cascadable = {k: v for k, v in updated_fields.items() if k in CASCADE_FIELDS}
    if not cascadable:
        return []

    # Find all PropertyTypes that inherit from this SharedPropertyType
    inheritors = await graph_repo.get_related_nodes(
        "SharedPropertyType",
        shared_rid,
        tenant_id,
        "BASED_ON",
        direction="incoming",
    )

    affected_rids: list[str] = []
    for prop_node in inheritors:
        prop_rid = prop_node.get("rid", "")
        updates: dict[str, Any] = {}
        for field, new_value in cascadable.items():
            if old_values is not None:
                # Value comparison: only cascade if the PropertyType's current value
                # matches the old SharedPropertyType value (meaning not overridden)
                old_val = old_values.get(field)
                current_val = prop_node.get(field)
                if current_val == old_val:
                    updates[field] = new_value
            else:
                # Legacy fallback: cascade unless _override_ flag is set
                if prop_node.get(f"_override_{field}") is not True:
                    updates[field] = new_value

        if updates:
            await graph_repo.update_node(
                "PropertyType", prop_rid, tenant_id, updates
            )
            affected_rids.append(prop_rid)

    return affected_rids
