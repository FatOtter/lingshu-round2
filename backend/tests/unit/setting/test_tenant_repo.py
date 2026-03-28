"""Tests for TenantRepository CRUD operations."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from lingshu.setting.models import Tenant
from lingshu.setting.repository.tenant_repo import TenantRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repo(mock_session: AsyncMock) -> TenantRepository:
    return TenantRepository(mock_session)


@pytest.fixture
def sample_tenant() -> Tenant:
    return Tenant(
        rid="ri.tenant.abc123",
        display_name="Test Tenant",
        status="active",
    )


@pytest.mark.asyncio
async def test_create_tenant(
    repo: TenantRepository, mock_session: AsyncMock, sample_tenant: Tenant
) -> None:
    """create() should add tenant to session and flush."""
    result = await repo.create(sample_tenant)

    mock_session.add.assert_called_once_with(sample_tenant)
    mock_session.flush.assert_awaited_once()
    assert result is sample_tenant


@pytest.mark.asyncio
async def test_get_by_rid_returns_tenant(
    repo: TenantRepository, mock_session: AsyncMock, sample_tenant: Tenant
) -> None:
    """get_by_rid() should return tenant when found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_tenant
    mock_session.execute.return_value = mock_result

    result = await repo.get_by_rid("ri.tenant.abc123")

    assert result is sample_tenant


@pytest.mark.asyncio
async def test_get_by_rid_returns_none(
    repo: TenantRepository, mock_session: AsyncMock
) -> None:
    """get_by_rid() should return None when tenant not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await repo.get_by_rid("ri.tenant.nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_list_all_paginated(
    repo: TenantRepository, mock_session: AsyncMock, sample_tenant: Tenant
) -> None:
    """list_all() should return (tenants, total) with pagination."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [sample_tenant]
    data_result = MagicMock()
    data_result.scalars.return_value = scalars_mock

    mock_session.execute.side_effect = [count_result, data_result]

    tenants, total = await repo.list_all(offset=0, limit=10)

    assert total == 1
    assert tenants == [sample_tenant]


@pytest.mark.asyncio
async def test_list_by_user(
    repo: TenantRepository, mock_session: AsyncMock, sample_tenant: Tenant
) -> None:
    """list_by_user() should return tenants the user belongs to."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [sample_tenant]
    data_result = MagicMock()
    data_result.scalars.return_value = scalars_mock

    mock_session.execute.side_effect = [count_result, data_result]

    tenants, total = await repo.list_by_user("ri.user.u1")

    assert total == 1
    assert tenants == [sample_tenant]


@pytest.mark.asyncio
async def test_update_fields(
    repo: TenantRepository, mock_session: AsyncMock, sample_tenant: Tenant
) -> None:
    """update_fields() should update and return refreshed tenant."""
    get_result = MagicMock()
    get_result.scalar_one_or_none.return_value = sample_tenant
    mock_session.execute.side_effect = [MagicMock(), get_result]

    result = await repo.update_fields("ri.tenant.abc123", display_name="Updated")

    assert result is sample_tenant
    mock_session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_count(
    repo: TenantRepository, mock_session: AsyncMock
) -> None:
    """count() should return total tenant count."""
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    mock_session.execute.return_value = mock_result

    result = await repo.count()

    assert result == 5
