"""Integration tests for data pipeline workflows: connections, editlog, branches."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.data.models import Connection
from lingshu.data.service import DataServiceImpl
from lingshu.infra.errors import AppError, ErrorCode


# ── Helpers ───────────────────────────────────────────────────────


def _make_connection(
    rid: str = "ri.conn.1",
    status: str = "disconnected",
    conn_type: str = "postgresql",
) -> Connection:
    c = Connection(
        rid=rid,
        tenant_id="t1",
        display_name="Test PG",
        type=conn_type,
        config={"host": "localhost", "port": 5432, "dbname": "test"},
        credentials="secret",
        status=status,
    )
    c.created_at = datetime.utcnow()
    c.updated_at = datetime.utcnow()
    return c


def _build_service() -> DataServiceImpl:
    ontology = AsyncMock()
    return DataServiceImpl(ontology_service=ontology, nessie_url="http://nessie:19120")


def _mock_session() -> AsyncMock:
    s = AsyncMock()
    s.commit = AsyncMock()
    return s


# ── Tests ─────────────────────────────────────────────────────────


class TestCreateTestQueryConnection:
    """Create connection -> test connection -> query connections."""

    async def test_create_and_test_flow(self) -> None:
        service = _build_service()
        session = _mock_session()
        conn = _make_connection()
        connected_conn = _make_connection(status="connected")

        with patch("lingshu.data.service.get_tenant_id", return_value="t1"):
            # Step 1: Create
            with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
                MockRepo.return_value.create = AsyncMock(return_value=conn)
                with patch("lingshu.data.service.generate_rid", return_value="ri.conn.1"):
                    result = await service.create_connection(
                        "Test PG", "postgresql",
                        {"host": "localhost", "port": 5432, "dbname": "test"},
                        "secret", session,
                    )
                assert result.rid == "ri.conn.1"
                assert result.status == "disconnected"

            # Step 2: Test connection
            with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
                MockRepo.return_value.get_by_rid = AsyncMock(return_value=conn)
                MockRepo.return_value.update_fields = AsyncMock(return_value=connected_conn)

                mock_connector = MagicMock()
                mock_connector.test_connection = AsyncMock(
                    return_value=MagicMock(success=True, latency_ms=5, server_version="15.2", error=None),
                )
                service._connectors["ri.conn.1"] = mock_connector

                test_result = await service.test_connection("ri.conn.1", session)
                assert test_result.success is True
                assert test_result.latency_ms == 5

            # Step 3: Query connections
            with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
                MockRepo.return_value.list_by_tenant = AsyncMock(
                    return_value=([connected_conn], 1),
                )
                conns, total = await service.query_connections(session)
                assert total == 1
                assert conns[0].rid == "ri.conn.1"


class TestWriteEditlogMerge:
    """Write editlog entry and verify it is persisted."""

    async def test_write_editlog(self) -> None:
        service = _build_service()
        session = _mock_session()

        with (
            patch("lingshu.data.service.get_tenant_id", return_value="t1"),
            patch.object(
                service._edit_log_store, "write", new=AsyncMock(return_value="entry_001"),
            ),
        ):
            entry_id = await service.write_editlog(
                type_rid="ri.obj.1",
                primary_key={"id": 42},
                operation="update",
                field_values={"status": "active"},
                user_id="u1",
                session=session,
            )
            assert entry_id == "entry_001"
            session.commit.assert_awaited_once()


class TestBranchCreateMergeDelete:
    """Branch create -> merge -> delete."""

    async def test_branch_lifecycle(self) -> None:
        service = _build_service()
        nessie = service._nessie
        assert nessie is not None

        nessie.create_branch = AsyncMock(return_value={"name": "feature-x", "hash": "abc123"})
        nessie.merge_branch = AsyncMock(return_value={"merged": True})
        nessie.get_branch = AsyncMock(return_value={"name": "feature-x", "hash": "abc123"})
        nessie.delete_branch = AsyncMock()

        # Create
        branch = await service.create_branch("feature-x", "main")
        assert branch["name"] == "feature-x"

        # Merge
        merge_result = await service.merge_branch("feature-x", "main")
        assert merge_result["merged"] is True

        # Delete
        await service.delete_branch("feature-x")
        nessie.delete_branch.assert_awaited_once_with("feature-x", "abc123")


class TestBranchDiff:
    """Diff between two branches."""

    async def test_diff_branches(self) -> None:
        service = _build_service()
        nessie = service._nessie
        nessie.diff_branches = AsyncMock(return_value=[{"key": "table1", "type": "PUT"}])

        diff = await service.diff_branches("feature-x", "main")
        assert len(diff) == 1
        assert diff[0]["key"] == "table1"


class TestConnectionNotFound:
    """Get a non-existent connection should fail."""

    async def test_get_missing_connection(self) -> None:
        service = _build_service()
        session = _mock_session()

        with (
            patch("lingshu.data.service.get_tenant_id", return_value="t1"),
            patch("lingshu.data.service.ConnectionRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_rid = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.get_connection("ri.conn.missing", session)
            assert exc_info.value.code == ErrorCode.DATA_SOURCE_NOT_FOUND


class TestBranchNotConfigured:
    """Branch operations without Nessie configured should fail."""

    async def test_no_nessie(self) -> None:
        service = DataServiceImpl(ontology_service=AsyncMock(), nessie_url=None)

        with pytest.raises(AppError) as exc_info:
            await service.list_branches()
        assert exc_info.value.code == ErrorCode.DATA_BRANCH_UNAVAILABLE
