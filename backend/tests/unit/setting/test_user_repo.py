"""Tests for UserRepository CRUD operations."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from lingshu.setting.models import User
from lingshu.setting.repository.user_repo import UserRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> UserRepository:
    return UserRepository(mock_session)


@pytest.fixture
def sample_user() -> User:
    return User(
        rid="ri.user.abc123",
        email="test@example.com",
        display_name="Test User",
        password_hash="hashed_pw",
        status="active",
    )


@pytest.mark.asyncio
async def test_create_user_adds_to_session(
    repo: UserRepository, mock_session: AsyncMock, sample_user: User
) -> None:
    """create() should add user to session and flush."""
    result = await repo.create(sample_user)

    mock_session.add.assert_called_once_with(sample_user)
    mock_session.flush.assert_awaited_once()
    assert result is sample_user


@pytest.mark.asyncio
async def test_get_by_rid_returns_user(
    repo: UserRepository, mock_session: AsyncMock, sample_user: User
) -> None:
    """get_by_rid() should return user when found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await repo.get_by_rid("ri.user.abc123")

    assert result is sample_user
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_rid_returns_none(
    repo: UserRepository, mock_session: AsyncMock
) -> None:
    """get_by_rid() should return None when user not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await repo.get_by_rid("ri.user.nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_get_by_email_returns_user(
    repo: UserRepository, mock_session: AsyncMock, sample_user: User
) -> None:
    """get_by_email() should return user when email matches."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await repo.get_by_email("test@example.com")

    assert result is sample_user


@pytest.mark.asyncio
async def test_get_by_email_returns_none(
    repo: UserRepository, mock_session: AsyncMock
) -> None:
    """get_by_email() should return None when email not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await repo.get_by_email("unknown@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_list_by_tenant_returns_paginated(
    repo: UserRepository, mock_session: AsyncMock, sample_user: User
) -> None:
    """list_by_tenant() should return (users, total) tuple."""
    # First call: count query
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    # Second call: data query
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [sample_user]
    data_result = MagicMock()
    data_result.scalars.return_value = scalars_mock

    mock_session.execute.side_effect = [count_result, data_result]

    users, total = await repo.list_by_tenant("ri.tenant.t1", offset=0, limit=20)

    assert total == 1
    assert users == [sample_user]
    assert mock_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_update_fields(
    repo: UserRepository, mock_session: AsyncMock, sample_user: User
) -> None:
    """update_fields() should execute update and return refreshed user."""
    # First call: update statement
    mock_session.execute.return_value = MagicMock()

    # After flush, get_by_rid is called internally
    get_result = MagicMock()
    get_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.side_effect = [MagicMock(), get_result]

    result = await repo.update_fields("ri.user.abc123", display_name="Updated")

    assert result is sample_user
    mock_session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_count(
    repo: UserRepository, mock_session: AsyncMock
) -> None:
    """count() should return total user count."""
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    mock_session.execute.return_value = mock_result

    result = await repo.count()

    assert result == 42
