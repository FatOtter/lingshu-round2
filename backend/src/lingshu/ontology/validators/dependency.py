"""Dependency detection: check incoming references before deletion."""

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.repository.graph_repo import GraphRepository

# Map entity type → (label, relationship types that indicate dependency)
DEPENDENCY_RULES: dict[str, list[tuple[str, str]]] = {
    "SharedPropertyType": [
        ("PropertyType", "BASED_ON"),
        ("InterfaceType", "REQUIRES"),
    ],
    "InterfaceType": [
        ("ObjectType", "IMPLEMENTS"),
        ("LinkType", "IMPLEMENTS"),
        ("InterfaceType", "EXTENDS"),
    ],
    "ObjectType": [
        ("LinkType", "CONNECTS"),
        ("ActionType", "OPERATES_ON"),
    ],
    "LinkType": [
        ("ActionType", "OPERATES_ON"),
    ],
    "ActionType": [],  # No dependencies, always deletable
    "PropertyType": [],  # Owned by parent, deleted with parent
}


async def check_delete_dependencies(
    graph_repo: GraphRepository,
    label: str,
    rid: str,
    tenant_id: str,
) -> None:
    """Raise AppError if entity has incoming references preventing deletion."""
    rules = DEPENDENCY_RULES.get(label, [])
    referencing_rids: list[str] = []

    for _dep_label, rel_type in rules:
        rids = await graph_repo.get_incoming_referencing_rids(
            label, rid, tenant_id, rel_type
        )
        referencing_rids.extend(rids)

    if referencing_rids:
        raise AppError(
            code=ErrorCode.ONTOLOGY_DEPENDENCY_CONFLICT,
            message=f"Cannot delete {label} {rid}: referenced by {len(referencing_rids)} entities",
            details={"referencing_rids": referencing_rids[:10]},
        )
