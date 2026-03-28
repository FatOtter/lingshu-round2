"""Tests for AuditLogRepository operations."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from lingshu.setting.models import AuditLog
from lingshu.setting.repository.audit_log_repo import AuditLogRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repo(mock_session: AsyncMock) -> AuditLogRepository:
    return AuditLogRepository(mock_session)


@pytest.fixture
def sample_log() -> AuditLog:
    return AuditLog(
        log_id=1,
        tenant_id="ri.tenant.t1",
        module="setting",
        event_type="user.create",
        user_id="ri.user.u1",
        action="Created user",
        resource_type="user",
        resource_rid="ri.user.u2",
    )


@pytest.mark.asyncio
async def test_create_audit_log(
    repo: AuditLogRepository, mock_session: AsyncMock, sample_log: AuditLog
) -> None:
    """create() should add audit log to session and flush."""
    result = await repo.create(sample_log)

    mock_session.add.assert_called_once_with(sample_log)
    mock_session.flush.assert_awaited_once()
    assert result is sample_log


@pytest.mark.asyncio
async def test_get_by_id_returns_log(
    repo: AuditLogRepository, mock_session: AsyncMock, sample_log: AuditLog
) -> None:
    """get_by_id() should return audit log when found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_log
    mock_session.execute.return_value = mock_result

    result = await repo.get_by_id(1, "ri.tenant.t1")

    assert result is sample_log


@pytest.mark.asyncio
async def test_query_with_no_filters(
    repo: AuditLogRepository, mock_session: AsyncMock, sample_log: AuditLog
) -> None:
    """query() with only tenant_id should return all logs for that tenant."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [sample_log]
    data_result = MagicMock()
    data_result.scalars.return_value = scalars_mock

    mock_session.execute.side_effect = [count_result, data_result]

    logs, total = await repo.query("ri.tenant.t1")

    assert total == 1
    assert logs == [sample_log]


@pytest.mark.asyncio
async def test_query_with_filters(
    repo: AuditLogRepository, mock_session: AsyncMock, sample_log: AuditLog
) -> None:
    """query() with filters should apply them to the query."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [sample_log]
    data_result = MagicMock()
    data_result.scalars.return_value = scalars_mock

    mock_session.execute.side_effect = [count_result, data_result]

    logs, total = await repo.query(
        "ri.tenant.t1",
        module="setting",
        event_type="user.create",
        user_id="ri.user.u1",
        resource_type="user",
        resource_rid="ri.user.u2",
    )

    assert total == 1
    assert logs == [sample_log]
    # Two execute calls: count + data
    assert mock_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_query_with_pagination(
    repo: AuditLogRepository, mock_session: AsyncMock
) -> None:
    """query() should respect offset and limit."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = 50

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    data_result = MagicMock()
    data_result.scalars.return_value = scalars_mock

    mock_session.execute.side_effect = [count_result, data_result]

    logs, total = await repo.query("ri.tenant.t1", offset=20, limit=10)

    assert total == 50
    assert logs == []


@pytest.mark.asyncio
async def test_delete_before(
    repo: AuditLogRepository, mock_session: AsyncMock
) -> None:
    """delete_before() should count and delete old logs."""
    from datetime import datetime, timezone

    count_result = MagicMock()
    count_result.scalar_one.return_value = 3
    mock_session.execute.side_effect = [count_result, MagicMock()]

    before = datetime(2026, 1, 1, tzinfo=timezone.utc)
    deleted = await repo.delete_before("ri.tenant.t1", before)

    assert deleted == 3
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_recent(
    repo: AuditLogRepository, mock_session: AsyncMock, sample_log: AuditLog
) -> None:
    """recent() should return the most recent logs."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [sample_log]
    mock_result = MagicMock()
    mock_result.scalars.return_value = scalars_mock
    mock_session.execute.return_value = mock_result

    logs = await repo.recent("ri.tenant.t1", limit=5)

    assert logs == [sample_log]
