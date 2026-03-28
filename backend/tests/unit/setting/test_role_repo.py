"""Unit tests for CustomRoleRepository CRUD operations."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.setting.repository.role_repo import CustomRoleRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    # session.add is a sync method on AsyncSession, use MagicMock to avoid warning
    session.add = MagicMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> CustomRoleRepository:
    return CustomRoleRepository(mock_session)


class TestCustomRoleCreate:
    async def test_create_adds_and_flushes(
        self, repo: CustomRoleRepository, mock_session: AsyncMock
    ) -> None:
        role = MagicMock()
        role.rid = "ri.role.1"
        result = await repo.create(role)
        mock_session.add.assert_called_once_with(role)
        mock_session.flush.assert_awaited_once()
        assert result is role


class TestCustomRoleGetByRid:
    async def test_get_by_rid_found(
        self, repo: CustomRoleRepository, mock_session: AsyncMock
    ) -> None:
        mock_role = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_role
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_rid("ri.role.1")
        assert result is mock_role

    async def test_get_by_rid_not_found(
        self, repo: CustomRoleRepository, mock_session: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_rid("ri.role.missing")
        assert result is None


class TestCustomRoleGetByName:
    async def test_get_by_name_found(
        self, repo: CustomRoleRepository, mock_session: AsyncMock
    ) -> None:
        mock_role = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_role
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_name("t1", "editor")
        assert result is mock_role


class TestCustomRoleUpdateFields:
    async def test_update_with_fields(
        self, repo: CustomRoleRepository, mock_session: AsyncMock
    ) -> None:
        mock_role = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_role
        # First call is update, second is get_by_rid
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_fields("ri.role.1", name="new_name")
        assert mock_session.flush.await_count >= 1
        assert result is mock_role

    async def test_update_no_fields_returns_current(
        self, repo: CustomRoleRepository, mock_session: AsyncMock
    ) -> None:
        mock_role = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_role
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_fields("ri.role.1")
        # Should just call get_by_rid, no update execute
        assert result is mock_role


class TestCustomRoleDelete:
    async def test_delete_executes_and_flushes(
        self, repo: CustomRoleRepository, mock_session: AsyncMock
    ) -> None:
        await repo.delete("ri.role.1")
        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()
