"""Neo4j schema initialization: create constraints and indexes for Ontology nodes."""

import asyncio
import sys

from neo4j import AsyncGraphDatabase

NODE_LABELS = [
    "SharedPropertyType",
    "PropertyType",
    "InterfaceType",
    "ObjectType",
    "LinkType",
    "ActionType",
]


async def init_neo4j_schema(uri: str, user: str, password: str) -> None:
    """Create uniqueness constraints and indexes for all Ontology node types."""
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            for label in NODE_LABELS:
                # RID uniqueness constraint (also creates an index)
                await session.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
                    f"REQUIRE n.rid IS UNIQUE"
                )
                # tenant_id index for tenant-scoped queries
                await session.run(
                    f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.tenant_id)"
                )
            print("Neo4j schema initialized successfully.")
    finally:
        await driver.close()


if __name__ == "__main__":
    uri = sys.argv[1] if len(sys.argv) > 1 else "bolt://localhost:7687"
    user = sys.argv[2] if len(sys.argv) > 2 else "neo4j"
    password = sys.argv[3] if len(sys.argv) > 3 else "password"
    asyncio.run(init_neo4j_schema(uri, user, password))
