"""InterfaceType contract validation: ensure implementors satisfy interface requirements."""

from typing import Any

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.repository.graph_repo import GraphRepository


async def check_contract_satisfaction(
    graph_repo: GraphRepository,
    interface_rid: str,
    tenant_id: str,
    required_shared_property_type_rids: list[str],
) -> list[dict[str, Any]]:
    """Check all ObjectTypes/LinkTypes implementing this interface satisfy its contract.

    Validates that all implementing entities have PropertyTypes based on
    every required SharedPropertyType in the interface.

    Args:
        graph_repo: The graph repository.
        interface_rid: RID of the InterfaceType.
        tenant_id: Tenant identifier.
        required_shared_property_type_rids: RIDs of required SharedPropertyTypes.

    Returns:
        List of violation dicts, each with 'entity_rid' and 'missing_rids'.

    Raises:
        AppError: If any implementors violate the contract.
    """
    if not required_shared_property_type_rids:
        return []

    # Find all entities that IMPLEMENTS this interface
    implementors = await graph_repo.get_related_nodes(
        "InterfaceType",
        interface_rid,
        tenant_id,
        "IMPLEMENTS",
        direction="incoming",
    )

    violations: list[dict[str, Any]] = []

    for implementor in implementors:
        entity_rid = implementor.get("rid", "")
        # Determine entity label from the node
        entity_label = _detect_entity_label(implementor)

        # Get PropertyTypes of this entity
        prop_nodes = await graph_repo.get_related_nodes(
            entity_label,
            entity_rid,
            tenant_id,
            "BELONGS_TO",
            direction="incoming",
        )

        # Collect which SharedPropertyTypes are covered via BASED_ON
        covered_shared_rids: set[str] = set()
        for prop_node in prop_nodes:
            inherit_rid = prop_node.get("inherit_from_shared_property_type_rid")
            if inherit_rid:
                covered_shared_rids.add(inherit_rid)

        missing = [
            rid for rid in required_shared_property_type_rids
            if rid not in covered_shared_rids
        ]

        if missing:
            violations.append({
                "entity_rid": entity_rid,
                "missing_shared_property_type_rids": missing,
            })

    if violations:
        raise AppError(
            code=ErrorCode.ONTOLOGY_CONTRACT_VIOLATION,
            message=(
                f"InterfaceType {interface_rid} contract violated by "
                f"{len(violations)} implementor(s)"
            ),
            details={"violations": violations},
        )

    return violations


def _detect_entity_label(node: dict[str, Any]) -> str:
    """Detect the Neo4j label of an entity from its properties."""
    # Check _label if available (set by graph queries), otherwise guess from rid
    label = node.get("_label", "")
    if label:
        return label

    rid = node.get("rid", "")
    if rid.startswith("ri.obj."):
        return "ObjectType"
    if rid.startswith("ri.link."):
        return "LinkType"

    return "ObjectType"  # default fallback
