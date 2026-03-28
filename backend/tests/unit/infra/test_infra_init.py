"""Unit tests for infrastructure init/close lifecycle: database, graph_db, redis."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# Database (database.py)
# ══════════════════════════════════════════════════════════════════


class TestDatabaseLifecycle:
    @pytest.mark.asyncio
    async def test_init_db_creates_engine_and_factory(self) -> None:
        with patch("lingshu.infra.database.create_async_engine") as mock_engine_fn, \
             patch("lingshu.infra.database.async_sessionmaker") as mock_factory_fn:
            mock_engine = MagicMock()
            mock_engine_fn.return_value = mock_engine

            from lingshu.infra.database import init_db
            await init_db("postgresql+asyncpg://test:test@localhost/test")

            mock_engine_fn.assert_called_once()
            mock_factory_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_db_disposes_engine(self) -> None:
        mock_engine = AsyncMock()
        import lingshu.infra.database as db_mod
        db_mod._engine = mock_engine
        db_mod._session_factory = MagicMock()

        from lingshu.infra.database import close_db
        await close_db()

        mock_engine.dispose.assert_awaited_once()
        assert db_mod._engine is None
        assert db_mod._session_factory is None

    @pytest.mark.asyncio
    async def test_close_db_noop_when_no_engine(self) -> None:
        import lingshu.infra.database as db_mod
        db_mod._engine = None
        db_mod._session_factory = None

        from lingshu.infra.database import close_db
        await close_db()

    @pytest.mark.asyncio
    async def test_get_session_raises_when_not_initialized(self) -> None:
        import lingshu.infra.database as db_mod
        db_mod._session_factory = None

        from lingshu.infra.database import get_session
        with pytest.raises(RuntimeError, match="Database not initialized"):
            async for _ in get_session():
                pass

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self) -> None:
        import lingshu.infra.database as db_mod

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = ctx

        db_mod._session_factory = mock_factory

        async for session in db_mod.get_session():
            assert session is mock_session

        db_mod._session_factory = None  # cleanup

    def test_get_engine_raises_when_not_initialized(self) -> None:
        import lingshu.infra.database as db_mod
        db_mod._engine = None

        from lingshu.infra.database import get_engine
        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_engine()

    def test_get_engine_returns_engine(self) -> None:
        import lingshu.infra.database as db_mod
        mock_engine = MagicMock()
        db_mod._engine = mock_engine

        from lingshu.infra.database import get_engine
        assert get_engine() is mock_engine
        db_mod._engine = None


# ══════════════════════════════════════════════════════════════════
# Graph DB (graph_db.py)
# ══════════════════════════════════════════════════════════════════


class TestGraphDbLifecycle:
    @pytest.mark.asyncio
    async def test_init_graph_db_creates_driver(self) -> None:
        mock_driver = AsyncMock()
        with patch(
            "lingshu.infra.graph_db.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            from lingshu.infra.graph_db import init_graph_db
            await init_graph_db("bolt://localhost:7687", "neo4j", "password")

            mock_driver.verify_connectivity.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_graph_db_closes_driver(self) -> None:
        mock_driver = AsyncMock()
        import lingshu.infra.graph_db as gdb_mod
        gdb_mod._driver = mock_driver

        from lingshu.infra.graph_db import close_graph_db
        await close_graph_db()

        mock_driver.close.assert_awaited_once()
        assert gdb_mod._driver is None

    @pytest.mark.asyncio
    async def test_close_graph_db_noop_when_none(self) -> None:
        import lingshu.infra.graph_db as gdb_mod
        gdb_mod._driver = None

        from lingshu.infra.graph_db import close_graph_db
        await close_graph_db()

    def test_get_driver_raises_when_not_initialized(self) -> None:
        import lingshu.infra.graph_db as gdb_mod
        gdb_mod._driver = None

        from lingshu.infra.graph_db import get_driver
        with pytest.raises(RuntimeError, match="Neo4j not initialized"):
            get_driver()

    def test_get_driver_returns_driver(self) -> None:
        import lingshu.infra.graph_db as gdb_mod
        mock_driver = MagicMock()
        gdb_mod._driver = mock_driver

        from lingshu.infra.graph_db import get_driver
        assert get_driver() is mock_driver
        gdb_mod._driver = None


# ══════════════════════════════════════════════════════════════════
# Redis (redis.py)
# ══════════════════════════════════════════════════════════════════


class TestRedisLifecycle:
    @pytest.mark.asyncio
    async def test_init_redis_creates_client(self) -> None:
        mock_client = AsyncMock()
        with patch(
            "lingshu.infra.redis.Redis.from_url",
            return_value=mock_client,
        ):
            from lingshu.infra.redis import init_redis
            await init_redis("redis://localhost:6379/0")

            mock_client.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_redis_closes_client(self) -> None:
        mock_client = AsyncMock()
        import lingshu.infra.redis as redis_mod
        redis_mod._redis = mock_client

        from lingshu.infra.redis import close_redis
        await close_redis()

        mock_client.aclose.assert_awaited_once()
        assert redis_mod._redis is None

    @pytest.mark.asyncio
    async def test_close_redis_noop_when_none(self) -> None:
        import lingshu.infra.redis as redis_mod
        redis_mod._redis = None

        from lingshu.infra.redis import close_redis
        await close_redis()

    def test_get_redis_raises_when_not_initialized(self) -> None:
        import lingshu.infra.redis as redis_mod
        redis_mod._redis = None

        from lingshu.infra.redis import get_redis
        with pytest.raises(RuntimeError, match="Redis not initialized"):
            get_redis()

    def test_get_redis_returns_client(self) -> None:
        import lingshu.infra.redis as redis_mod
        mock_client = MagicMock()
        redis_mod._redis = mock_client

        from lingshu.infra.redis import get_redis
        assert get_redis() is mock_client
        redis_mod._redis = None
