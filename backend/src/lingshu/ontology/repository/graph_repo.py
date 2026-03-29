"""Neo4j graph repository: CRUD for Ontology nodes and relationships."""

from typing import Any

from neo4j import AsyncDriver

# Entity type to Neo4j label mapping
ENTITY_LABELS: dict[str, str] = {
    "object_type": "ObjectType",
    "link_type": "LinkType",
    "interface_type": "InterfaceType",
    "shared_property_type": "SharedPropertyType",
    "property_type": "PropertyType",
    "action_type": "ActionType",
}

# Fields stored as JSON strings in Neo4j (complex nested structures)
JSON_FIELDS = frozenset({
    "widget",
    "validation",
    "compliance",
    "parameters",
    "execution",
    "side_effects",
    "link_requirements",
    "object_constraint",
    "asset_mapping",
    "entity_validation",
})


class GraphRepository:
    """Neo4j repository for Ontology entity nodes and relationships."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    # ── Node CRUD ─────────────────────────────────────────────────

    async def create_node(
        self,
        label: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new node with the given label and properties."""
        query = f"CREATE (n:{label} $props) RETURN n"
        async with self._driver.session() as session:
            result = await session.run(query, props=properties)
            record = await result.single()
            return dict(record["n"]) if record else {}

    async def get_node(
        self,
        label: str,
        rid: str,
        tenant_id: str,
    ) -> dict[str, Any] | None:
        """Get a single node by RID and tenant_id."""
        query = (
            f"MATCH (n:{label} {{rid: $rid, tenant_id: $tenant_id}}) "
            "RETURN n"
        )
        async with self._driver.session() as session:
            result = await session.run(query, rid=rid, tenant_id=tenant_id)
            record = await result.single()
            return dict(record["n"]) if record else None

    async def get_active_node(
        self,
        label: str,
        rid: str,
        tenant_id: str,
    ) -> dict[str, Any] | None:
        """Get the Active version of a node."""
        query = (
            f"MATCH (n:{label} {{rid: $rid, tenant_id: $tenant_id, "
            "is_draft: false, is_staging: false, is_active: true}) "
            "RETURN n"
        )
        async with self._driver.session() as session:
            result = await session.run(query, rid=rid, tenant_id=tenant_id)
            record = await result.single()
            return dict(record["n"]) if record else None

    async def get_draft_node(
        self,
        label: str,
        rid: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Get the Draft version of a node owned by user."""
        query = (
            f"MATCH (n:{label} {{rid: $rid, tenant_id: $tenant_id, "
            "is_draft: true, draft_owner: $user_id}) "
            "RETURN n"
        )
        async with self._driver.session() as session:
            result = await session.run(
                query, rid=rid, tenant_id=tenant_id, user_id=user_id
            )
            record = await result.single()
            return dict(record["n"]) if record else None

    async def get_staging_node(
        self,
        label: str,
        rid: str,
        tenant_id: str,
    ) -> dict[str, Any] | None:
        """Get the Staging version of a node."""
        query = (
            f"MATCH (n:{label} {{rid: $rid, tenant_id: $tenant_id, "
            "is_staging: true}) "
            "RETURN n"
        )
        async with self._driver.session() as session:
            result = await session.run(query, rid=rid, tenant_id=tenant_id)
            record = await result.single()
            return dict(record["n"]) if record else None

    async def get_effective_node(
        self,
        label: str,
        rid: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Get the most current version: Draft > Staging > Active."""
        # Try Draft first
        node = await self.get_draft_node(label, rid, tenant_id, user_id)
        if node:
            return node
        # Try Staging
        node = await self.get_staging_node(label, rid, tenant_id)
        if node:
            return node
        # Fall back to Active
        return await self.get_active_node(label, rid, tenant_id)

    async def update_node(
        self,
        label: str,
        rid: str,
        tenant_id: str,
        properties: dict[str, Any],
        *,
        is_draft: bool | None = None,
        draft_owner: str | None = None,
    ) -> dict[str, Any] | None:
        """Update node properties. Targets Draft if is_draft/draft_owner set."""
        conditions = "rid: $rid, tenant_id: $tenant_id"
        params: dict[str, Any] = {"rid": rid, "tenant_id": tenant_id, "props": properties}

        if is_draft is not None:
            conditions += ", is_draft: $is_draft"
            params["is_draft"] = is_draft
        if draft_owner is not None:
            conditions += ", draft_owner: $draft_owner"
            params["draft_owner"] = draft_owner

        query = (
            f"MATCH (n:{label} {{{conditions}}}) "
            "SET n += $props RETURN n"
        )
        async with self._driver.session() as session:
            result = await session.run(query, **params)
            record = await result.single()
            return dict(record["n"]) if record else None

    async def delete_node(
        self,
        label: str,
        rid: str,
        tenant_id: str,
        *,
        is_draft: bool | None = None,
        is_staging: bool | None = None,
        draft_owner: str | None = None,
    ) -> bool:
        """Delete a node. Returns True if a node was deleted."""
        conditions = "rid: $rid, tenant_id: $tenant_id"
        params: dict[str, Any] = {"rid": rid, "tenant_id": tenant_id}

        if is_draft is not None:
            conditions += ", is_draft: $is_draft"
            params["is_draft"] = is_draft
        if is_staging is not None:
            conditions += ", is_staging: $is_staging"
            params["is_staging"] = is_staging
        if draft_owner is not None:
            conditions += ", draft_owner: $draft_owner"
            params["draft_owner"] = draft_owner

        query = (
            f"MATCH (n:{label} {{{conditions}}}) "
            "DETACH DELETE n RETURN count(n) AS deleted"
        )
        async with self._driver.session() as session:
            result = await session.run(query, **params)
            record = await result.single()
            return record is not None and record["deleted"] > 0

    # ── List / Query ──────────────────────────────────────────────

    async def list_nodes(
        self,
        label: str,
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        include_drafts: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """List nodes with optional filters and search.

        When include_drafts is True, returns both active and draft nodes.
        Otherwise only returns committed active nodes.
        """
        where_parts: list[str] = ["n.tenant_id = $tenant_id"]
        if include_drafts:
            where_parts.append("(n.is_active = true OR n.is_draft = true)")
        else:
            where_parts.extend([
                "n.is_draft = false",
                "n.is_staging = false",
                "n.is_active = true",
            ])
        return await self._list_nodes_with_where(
            label, where_parts, tenant_id,
            offset=offset, limit=limit,
            filters=filters, search=search,
        )

    async def list_active_nodes(
        self,
        label: str,
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List Active nodes with optional filters and search."""
        where_parts = [
            "n.tenant_id = $tenant_id",
            "n.is_draft = false",
            "n.is_staging = false",
            "n.is_active = true",
        ]
        return await self._list_nodes_with_where(
            label, where_parts, tenant_id,
            offset=offset, limit=limit,
            filters=filters, search=search,
        )

    async def _list_nodes_with_where(
        self,
        label: str,
        where_parts: list[str],
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Shared helper for list queries with pre-built WHERE parts."""
        params: dict[str, Any] = {"tenant_id": tenant_id, "offset": offset, "limit": limit}

        if filters:
            for key, value in filters.items():
                param_key = f"f_{key}"
                where_parts.append(f"n.{key} = ${param_key}")
                params[param_key] = value

        if search:
            where_parts.append(
                "(n.api_name CONTAINS $search OR "
                "n.display_name CONTAINS $search OR "
                "n.description CONTAINS $search)"
            )
            params["search"] = search

        where_clause = " AND ".join(where_parts)

        count_query = f"MATCH (n:{label}) WHERE {where_clause} RETURN count(n) AS total"
        data_query = (
            f"MATCH (n:{label}) WHERE {where_clause} "
            "RETURN n ORDER BY n.created_at DESC SKIP $offset LIMIT $limit"
        )

        async with self._driver.session() as session:
            count_result = await session.run(count_query, **params)
            count_record = await count_result.single()
            total = count_record["total"] if count_record else 0

            data_result = await session.run(data_query, **params)
            nodes = [dict(record["n"]) async for record in data_result]

        return nodes, total

    # ── Relationships ─────────────────────────────────────────────

    async def create_relationship(
        self,
        from_label: str,
        from_rid: str,
        to_label: str,
        to_rid: str,
        rel_type: str,
        tenant_id: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """Create a relationship between two nodes."""
        props_clause = " $props" if properties else ""
        query = (
            f"MATCH (a:{from_label} {{rid: $from_rid, tenant_id: $tenant_id}}) "
            f"MATCH (b:{to_label} {{rid: $to_rid, tenant_id: $tenant_id}}) "
            f"CREATE (a)-[r:{rel_type}{props_clause}]->(b) "
            "RETURN type(r) AS rel"
        )
        params: dict[str, Any] = {
            "from_rid": from_rid,
            "to_rid": to_rid,
            "tenant_id": tenant_id,
        }
        if properties:
            params["props"] = properties
        async with self._driver.session() as session:
            result = await session.run(query, **params)
            record = await result.single()
            return record is not None

    async def delete_relationships(
        self,
        label: str,
        rid: str,
        tenant_id: str,
        rel_type: str | None = None,
        *,
        direction: str = "both",
    ) -> int:
        """Delete relationships from/to a node. Returns count deleted."""
        if direction == "outgoing":
            pattern = f"(n)-[r:{rel_type}]->()" if rel_type else "(n)-[r]->()"
        elif direction == "incoming":
            pattern = f"()-[r:{rel_type}]->(n)" if rel_type else "()-[r]->(n)"
        else:
            pattern = f"(n)-[r:{rel_type}]-()" if rel_type else "(n)-[r]-()"

        query = (
            f"MATCH (n:{label} {{rid: $rid, tenant_id: $tenant_id}}) "
            f"MATCH {pattern} "
            "DELETE r RETURN count(r) AS deleted"
        )
        async with self._driver.session() as session:
            result = await session.run(query, rid=rid, tenant_id=tenant_id)
            record = await result.single()
            return record["deleted"] if record else 0

    async def get_related_nodes(
        self,
        label: str,
        rid: str,
        tenant_id: str,
        rel_type: str,
        *,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Get nodes related to the given node via a relationship type."""
        if direction == "outgoing":
            pattern = f"(n)-[:{rel_type}]->(m)"
        elif direction == "incoming":
            pattern = f"(m)-[:{rel_type}]->(n)"
        else:
            pattern = f"(n)-[:{rel_type}]-(m)"

        query = (
            f"MATCH (n:{label} {{rid: $rid, tenant_id: $tenant_id}}) "
            f"MATCH {pattern} "
            "RETURN m"
        )
        async with self._driver.session() as session:
            result = await session.run(query, rid=rid, tenant_id=tenant_id)
            return [dict(record["m"]) async for record in result]

    # ── Dependency Checks ─────────────────────────────────────────

    async def count_incoming_references(
        self,
        label: str,
        rid: str,
        tenant_id: str,
        rel_type: str | None = None,
    ) -> int:
        """Count incoming references to a node (for dependency checks)."""
        pattern = f"()-[:{rel_type}]->(n)" if rel_type else "()-[]->(n)"

        query = (
            f"MATCH (n:{label} {{rid: $rid, tenant_id: $tenant_id}}) "
            f"MATCH {pattern} "
            "RETURN count(*) AS cnt"
        )
        async with self._driver.session() as session:
            result = await session.run(query, rid=rid, tenant_id=tenant_id)
            record = await result.single()
            return record["cnt"] if record else 0

    async def get_incoming_referencing_rids(
        self,
        label: str,
        rid: str,
        tenant_id: str,
        rel_type: str | None = None,
    ) -> list[str]:
        """Get RIDs of nodes that reference the given node."""
        pattern = f"(m)-[:{rel_type}]->(n)" if rel_type else "(m)-[]->(n)"

        query = (
            f"MATCH (n:{label} {{rid: $rid, tenant_id: $tenant_id}}) "
            f"MATCH {pattern} "
            "RETURN m.rid AS rid"
        )
        async with self._driver.session() as session:
            result = await session.run(query, rid=rid, tenant_id=tenant_id)
            return [record["rid"] async for record in result]

    # ── Topology ──────────────────────────────────────────────────

    async def get_topology(
        self, tenant_id: str
    ) -> dict[str, Any]:
        """Get full ontology topology for visualization."""
        nodes_query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id "
            "AND n.is_draft = false AND n.is_staging = false AND n.is_active = true "
            "RETURN n.rid AS rid, labels(n)[0] AS label, "
            "n.api_name AS api_name, n.display_name AS display_name"
        )
        edges_query = (
            "MATCH (a)-[r]->(b) "
            "WHERE a.tenant_id = $tenant_id "
            "AND a.is_active = true AND a.is_draft = false AND a.is_staging = false "
            "AND b.is_active = true AND b.is_draft = false AND b.is_staging = false "
            "RETURN a.rid AS source, b.rid AS target, type(r) AS rel_type"
        )
        async with self._driver.session() as session:
            nodes_result = await session.run(nodes_query, tenant_id=tenant_id)
            nodes = [
                dict(record) async for record in nodes_result
            ]
            edges_result = await session.run(edges_query, tenant_id=tenant_id)
            edges = [
                dict(record) async for record in edges_result
            ]

        return {"nodes": nodes, "edges": edges}

    # ── Search ────────────────────────────────────────────────────

    async def search_nodes(
        self,
        tenant_id: str,
        query: str,
        *,
        labels: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search across entity types by api_name, display_name, description."""
        label_filter = ""
        if labels:
            label_conditions = " OR ".join(f"n:{lbl}" for lbl in labels)
            label_filter = f"AND ({label_conditions}) "

        cypher = (
            "MATCH (n) "
            "WHERE n.tenant_id = $tenant_id "
            "AND n.is_draft = false AND n.is_staging = false AND n.is_active = true "
            f"{label_filter}"
            "AND (n.api_name CONTAINS $search_term OR "
            "n.display_name CONTAINS $search_term OR "
            "n.description CONTAINS $search_term) "
            "RETURN n, labels(n)[0] AS entity_type "
            "LIMIT $limit"
        )
        async with self._driver.session() as session:
            result = await session.run(
                cypher, tenant_id=tenant_id, search_term=query, limit=limit
            )
            results = []
            async for record in result:
                node_data = dict(record["n"])
                node_data["_entity_type"] = record["entity_type"]
                results.append(node_data)
            return results

    # ── Staging/Draft Summaries ───────────────────────────────────

    async def get_staging_summary(
        self, tenant_id: str
    ) -> dict[str, int]:
        """Count Staging entities by type."""
        query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id AND n.is_staging = true "
            "RETURN labels(n)[0] AS label, count(n) AS cnt"
        )
        async with self._driver.session() as session:
            result = await session.run(query, tenant_id=tenant_id)
            return {record["label"]: record["cnt"] async for record in result}

    async def get_staging_nodes(
        self, tenant_id: str
    ) -> list[dict[str, Any]]:
        """Get all Staging nodes for a tenant."""
        query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id AND n.is_staging = true "
            "RETURN n, labels(n)[0] AS label"
        )
        async with self._driver.session() as session:
            result = await session.run(query, tenant_id=tenant_id)
            nodes = []
            async for record in result:
                node_data = dict(record["n"])
                node_data["_label"] = record["label"]
                nodes.append(node_data)
            return nodes

    async def get_drafts_summary(
        self, tenant_id: str, user_id: str
    ) -> dict[str, int]:
        """Count Draft entities by type for a user."""
        query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id "
            "AND n.is_draft = true AND n.draft_owner = $user_id "
            "RETURN labels(n)[0] AS label, count(n) AS cnt"
        )
        async with self._driver.session() as session:
            result = await session.run(
                query, tenant_id=tenant_id, user_id=user_id
            )
            return {record["label"]: record["cnt"] async for record in result}

    # ── Batch Staging → Active ────────────────────────────────────

    async def promote_staging_to_active(
        self,
        tenant_id: str,
        snapshot_id: str,
    ) -> int:
        """Promote all Staging nodes to Active. Returns count promoted."""
        # First, mark old Active nodes as historical for entities that have Staging
        deactivate_query = (
            "MATCH (staging) WHERE staging.tenant_id = $tenant_id AND staging.is_staging = true "
            "WITH collect(staging.rid) AS staging_rids "
            "MATCH (active) WHERE active.tenant_id = $tenant_id "
            "AND active.is_active = true AND active.is_draft = false AND active.is_staging = false "
            "AND active.rid IN staging_rids "
            "SET active.is_active = false "
            "RETURN count(active) AS deactivated"
        )

        # Then promote Staging to Active
        promote_query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id AND n.is_staging = true "
            "SET n.is_staging = false, n.snapshot_id = $snapshot_id "
            "RETURN count(n) AS promoted"
        )

        # Handle deletion markers (is_active=false in Staging means delete)
        cleanup_query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id "
            "AND n.snapshot_id = $snapshot_id AND n.is_active = false "
            "DETACH DELETE n "
            "RETURN count(n) AS cleaned"
        )

        async with self._driver.session() as session:
            await session.run(deactivate_query, tenant_id=tenant_id)
            result = await session.run(
                promote_query, tenant_id=tenant_id, snapshot_id=snapshot_id
            )
            record = await result.single()
            promoted = record["promoted"] if record else 0
            await session.run(
                cleanup_query, tenant_id=tenant_id, snapshot_id=snapshot_id
            )
            return promoted

    async def rollback_to_snapshot(
        self,
        tenant_id: str,
        target_snapshot_id: str,
        current_snapshot_id: str,
    ) -> int:
        """Rollback: deactivate current, reactivate target snapshot nodes."""
        # Deactivate current Active
        deactivate_query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id "
            "AND n.snapshot_id = $current_id AND n.is_active = true "
            "SET n.is_active = false "
            "RETURN count(n) AS deactivated"
        )
        # Reactivate target snapshot
        reactivate_query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id "
            "AND n.snapshot_id = $target_id "
            "SET n.is_active = true "
            "RETURN count(n) AS reactivated"
        )
        async with self._driver.session() as session:
            await session.run(
                deactivate_query,
                tenant_id=tenant_id,
                current_id=current_snapshot_id,
            )
            result = await session.run(
                reactivate_query,
                tenant_id=tenant_id,
                target_id=target_snapshot_id,
            )
            record = await result.single()
            return record["reactivated"] if record else 0

    async def check_api_name_unique(
        self,
        label: str,
        api_name: str,
        tenant_id: str,
        *,
        exclude_rid: str | None = None,
    ) -> bool:
        """Check if api_name is unique among Active nodes of the same type."""
        exclude = ""
        params: dict[str, Any] = {
            "api_name": api_name,
            "tenant_id": tenant_id,
        }
        if exclude_rid:
            exclude = "AND n.rid <> $exclude_rid "
            params["exclude_rid"] = exclude_rid

        query = (
            f"MATCH (n:{label}) WHERE n.tenant_id = $tenant_id "
            "AND n.api_name = $api_name "
            "AND n.is_active = true AND n.is_draft = false AND n.is_staging = false "
            f"{exclude}"
            "RETURN count(n) AS cnt"
        )
        async with self._driver.session() as session:
            result = await session.run(query, **params)
            record = await result.single()
            return record is not None and record["cnt"] == 0

    async def has_uncommitted_changes(self, tenant_id: str) -> bool:
        """Check if tenant has any Draft or Staging nodes."""
        query = (
            "MATCH (n) WHERE n.tenant_id = $tenant_id "
            "AND (n.is_draft = true OR n.is_staging = true) "
            "RETURN count(n) AS cnt"
        )
        async with self._driver.session() as session:
            result = await session.run(query, tenant_id=tenant_id)
            record = await result.single()
            return record is not None and record["cnt"] > 0
