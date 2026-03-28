"""Tests for DataServiceImpl: connection management, branches, and write-back."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from lingshu.data.models import Connection
from lingshu.data.service import DataServiceImpl
from lingshu.data.schemas.responses import ConnectionResponse, ConnectionTestResponse
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def mock_ontology() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(mock_ontology: MagicMock) -> DataServiceImpl:
    return DataServiceImpl(ontology_service=mock_ontology, nessie_url=None)


@pytest.fixture
def service_with_nessie(mock_ontology: MagicMock) -> DataServiceImpl:
    with patch("lingshu.data.service.NessieClient") as mock_nessie_cls:
        mock_nessie_cls.return_value = AsyncMock()
        svc = DataServiceImpl(ontology_service=mock_ontology, nessie_url="http://nessie:19120")
        return svc


@pytest.fixture
def sample_connection() -> Connection:
    return Connection(
        rid="ri.conn.c1",
        tenant_id="ri.tenant.t1",
        display_name="Test DB",
        type="postgresql",
        config={"host": "localhost", "port": 5432},
        credentials="secret",
        status="connected",
        status_message=None,
        last_tested_at=None,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


# ── Connection Management Tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_create_connection_success(
    service: DataServiceImpl, mock_session: AsyncMock
) -> None:
    """create_connection() should create and return ConnectionResponse."""
    with patch("lingshu.data.service.get_tenant_id", return_value="ri.tenant.t1"):
        with patch("lingshu.data.service.generate_rid", return_value="ri.conn.new1"):
            with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
                mock_repo = AsyncMock()
                conn = Connection(
                    rid="ri.conn.new1",
                    tenant_id="ri.tenant.t1",
                    display_name="New DB",
                    type="postgresql",
                    config={"host": "localhost"},
                    credentials=None,
                    status="disconnected",
                )
                mock_repo.create.return_value = conn
                MockRepo.return_value = mock_repo

                result = await service.create_connection(
                    display_name="New DB",
                    conn_type="postgresql",
                    config={"host": "localhost"},
                    credentials=None,
                    session=mock_session,
                )

    assert isinstance(result, ConnectionResponse)
    assert result.rid == "ri.conn.new1"
    assert result.display_name == "New DB"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_connection_success(
    service: DataServiceImpl, mock_session: AsyncMock, sample_connection: Connection
) -> None:
    """update_connection() should update fields and return response."""
    with patch("lingshu.data.service.get_tenant_id", return_value="ri.tenant.t1"):
        with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.update_fields.return_value = sample_connection
            MockRepo.return_value = mock_repo

            result = await service.update_connection(
                "ri.conn.c1", {"display_name": "Updated"}, mock_session
            )

    assert isinstance(result, ConnectionResponse)
    assert result.rid == "ri.conn.c1"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_connection_not_found(
    service: DataServiceImpl, mock_session: AsyncMock
) -> None:
    """update_connection() should raise AppError when connection not found."""
    with patch("lingshu.data.service.get_tenant_id", return_value="ri.tenant.t1"):
        with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.update_fields.return_value = None
            MockRepo.return_value = mock_repo

            with pytest.raises(AppError) as exc_info:
                await service.update_connection(
                    "ri.conn.missing", {"display_name": "X"}, mock_session
                )

    assert exc_info.value.code == ErrorCode.DATA_SOURCE_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_connection_success(
    service: DataServiceImpl, mock_session: AsyncMock
) -> None:
    """delete_connection() should delete and commit."""
    with patch("lingshu.data.service.get_tenant_id", return_value="ri.tenant.t1"):
        with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.delete.return_value = True
            MockRepo.return_value = mock_repo

            await service.delete_connection("ri.conn.c1", mock_session)

    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_connection_not_found(
    service: DataServiceImpl, mock_session: AsyncMock
) -> None:
    """delete_connection() should raise AppError when connection not found."""
    with patch("lingshu.data.service.get_tenant_id", return_value="ri.tenant.t1"):
        with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.delete.return_value = False
            MockRepo.return_value = mock_repo

            with pytest.raises(AppError) as exc_info:
                await service.delete_connection("ri.conn.missing", mock_session)

    assert exc_info.value.code == ErrorCode.DATA_SOURCE_NOT_FOUND


@pytest.mark.asyncio
async def test_test_connection_success(
    service: DataServiceImpl, mock_session: AsyncMock, sample_connection: Connection
) -> None:
    """test_connection() should test and update status on success."""
    mock_test_result = MagicMock()
    mock_test_result.success = True
    mock_test_result.latency_ms = 5.0
    mock_test_result.server_version = "15.2"
    mock_test_result.error = None

    with patch("lingshu.data.service.get_tenant_id", return_value="ri.tenant.t1"):
        with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_rid.return_value = sample_connection
            mock_repo.update_fields.return_value = sample_connection
            MockRepo.return_value = mock_repo

            with patch.object(service, "_get_or_create_connector") as mock_get_conn:
                mock_connector = AsyncMock()
                mock_connector.test_connection.return_value = mock_test_result
                mock_get_conn.return_value = mock_connector

                result = await service.test_connection("ri.conn.c1", mock_session)

    assert isinstance(result, ConnectionTestResponse)
    assert result.success is True
    assert result.latency_ms == 5.0


@pytest.mark.asyncio
async def test_test_connection_failure(
    service: DataServiceImpl, mock_session: AsyncMock, sample_connection: Connection
) -> None:
    """test_connection() should update status to error on failure."""
    mock_test_result = MagicMock()
    mock_test_result.success = False
    mock_test_result.latency_ms = 0
    mock_test_result.server_version = None
    mock_test_result.error = "Connection refused"

    with patch("lingshu.data.service.get_tenant_id", return_value="ri.tenant.t1"):
        with patch("lingshu.data.service.ConnectionRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_by_rid.return_value = sample_connection
            mock_repo.update_fields.return_value = sample_connection
            MockRepo.return_value = mock_repo

            with patch.object(service, "_get_or_create_connector") as mock_get_conn:
                mock_connector = AsyncMock()
                mock_connector.test_connection.return_value = mock_test_result
                mock_get_conn.return_value = mock_connector

                result = await service.test_connection("ri.conn.c1", mock_session)

    assert result.success is False
    assert result.error == "Connection refused"


# ── Branch Management Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_list_branches_without_nessie(service: DataServiceImpl) -> None:
    """list_branches() should raise when Nessie is not configured."""
    with pytest.raises(AppError) as exc_info:
        await service.list_branches()

    assert exc_info.value.code == ErrorCode.DATA_BRANCH_UNAVAILABLE


@pytest.mark.asyncio
async def test_list_branches_with_nessie(
    service_with_nessie: DataServiceImpl,
) -> None:
    """list_branches() should delegate to NessieClient."""
    service_with_nessie._nessie.list_branches.return_value = [  # type: ignore[union-attr]
        {"name": "main", "hash": "abc123"}
    ]

    result = await service_with_nessie.list_branches()

    assert result == [{"name": "main", "hash": "abc123"}]


@pytest.mark.asyncio
async def test_create_branch(service_with_nessie: DataServiceImpl) -> None:
    """create_branch() should delegate to NessieClient."""
    service_with_nessie._nessie.create_branch.return_value = {  # type: ignore[union-attr]
        "name": "feature-1", "hash": "def456"
    }

    result = await service_with_nessie.create_branch("feature-1")

    assert result["name"] == "feature-1"


@pytest.mark.asyncio
async def test_merge_branch(service_with_nessie: DataServiceImpl) -> None:
    """merge_branch() should delegate to NessieClient."""
    service_with_nessie._nessie.merge_branch.return_value = {  # type: ignore[union-attr]
        "result": "merged"
    }

    result = await service_with_nessie.merge_branch("feature-1", "main")

    assert result["result"] == "merged"


# ── Write-Back Pipeline Tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_write_editlog(
    service: DataServiceImpl, mock_session: AsyncMock
) -> None:
    """write_editlog() should create entry and commit."""
    with patch("lingshu.data.service.get_tenant_id", return_value="ri.tenant.t1"):
        with patch("lingshu.data.service.make_entry") as mock_make:
            mock_entry = MagicMock()
            mock_make.return_value = mock_entry
            service._edit_log_store = AsyncMock()
            service._edit_log_store.write.return_value = "entry-123"

            result = await service.write_editlog(
                type_rid="ri.obj.o1",
                primary_key={"id": 1},
                operation="update",
                field_values={"name": "new"},
                user_id="ri.user.u1",
                session=mock_session,
            )

    assert result == "entry-123"
    mock_session.commit.assert_awaited_once()


# ── Helper Tests ─────────────────────────────────────────────


def test_get_or_create_connector_postgresql(
    service: DataServiceImpl, sample_connection: Connection
) -> None:
    """_get_or_create_connector() should create PostgreSQLConnector for postgresql type."""
    with patch("lingshu.data.service.PostgreSQLConnector") as MockPg:
        mock_pg = MagicMock()
        MockPg.return_value = mock_pg

        connector = service._get_or_create_connector(sample_connection)

    assert connector is mock_pg
    # Should be cached
    assert "ri.conn.c1" in service._connectors


def test_get_or_create_connector_unsupported_type(
    service: DataServiceImpl,
) -> None:
    """_get_or_create_connector() should raise for unsupported types."""
    conn = Connection(
        rid="ri.conn.bad",
        tenant_id="ri.tenant.t1",
        display_name="Bad",
        type="mysql",
        config={},
    )

    with pytest.raises(AppError) as exc_info:
        service._get_or_create_connector(conn)

    assert exc_info.value.code == ErrorCode.DATA_SOURCE_UNREACHABLE
