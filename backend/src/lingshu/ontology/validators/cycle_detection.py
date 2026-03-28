"""Cycle detection for InterfaceType EXTENDS relationships using DFS."""

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.repository.graph_repo import GraphRepository


async def check_interface_cycle(
    graph_repo: GraphRepository,
    interface_rid: str,
    extends_rids: list[str],
    tenant_id: str,
) -> None:
    """Detect cycles in InterfaceType EXTENDS graph.

    Raises AppError if adding extends_rids to interface_rid creates a cycle.
    """
    if not extends_rids:
        return

    # Build adjacency for DFS: we need to check if any extends_rid
    # can reach interface_rid through existing EXTENDS edges
    visited: set[str] = set()

    async def can_reach(current: str, target: str) -> bool:
        if current == target:
            return True
        if current in visited:
            return False
        visited.add(current)

        children = await graph_repo.get_related_nodes(
            "InterfaceType",
            current,
            tenant_id,
            "EXTENDS",
            direction="outgoing",
        )
        for child in children:
            child_rid = child.get("rid", "")
            if await can_reach(child_rid, target):
                return True
        return False

    for parent_rid in extends_rids:
        visited.clear()
        if await can_reach(parent_rid, interface_rid):
            raise AppError(
                code=ErrorCode.ONTOLOGY_CYCLE_DETECTED,
                message=(
                    f"Circular dependency: {interface_rid} extending {parent_rid} "
                    f"creates a cycle"
                ),
                details={
                    "interface_rid": interface_rid,
                    "parent_rid": parent_rid,
                },
            )
