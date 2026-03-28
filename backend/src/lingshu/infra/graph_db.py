"""Neo4j async driver connection management."""

from neo4j import AsyncDriver, AsyncGraphDatabase

_driver: AsyncDriver | None = None


async def init_graph_db(uri: str, user: str, password: str) -> None:
    """Initialize Neo4j async driver."""
    global _driver
    _driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    await _driver.verify_connectivity()


async def close_graph_db() -> None:
    """Close Neo4j driver."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


def get_driver() -> AsyncDriver:
    """Return the current Neo4j async driver."""
    if _driver is None:
        raise RuntimeError("Neo4j not initialized. Call init_graph_db() first.")
    return _driver
