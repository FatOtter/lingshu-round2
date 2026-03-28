"""Unit tests for SkillManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.infra.skills import SkillManager
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def manager() -> SkillManager:
    return SkillManager()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


class TestSkillManager:
    @pytest.mark.asyncio
    async def test_register_skill(
        self, manager: SkillManager, mock_session: AsyncMock,
    ) -> None:
        with patch(
            "lingshu.copilot.infra.skills.get_tenant_id",
            return_value="t1",
        ):
            result = await manager.register(
                mock_session,
                api_name="summarizer",
                display_name="Summarizer",
                description="Summarizes text",
                system_prompt="You are a summarizer.",
                tool_bindings=[{"tool": "search"}],
            )
        assert result.rid.startswith("ri.skill.")
        assert result.api_name == "summarizer"
        assert result.display_name == "Summarizer"
        assert result.description == "Summarizes text"
        assert result.system_prompt == "You are a summarizer."
        assert result.tool_bindings == [{"tool": "search"}]
        assert result.enabled is True
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_skill_defaults(
        self, manager: SkillManager, mock_session: AsyncMock,
    ) -> None:
        with patch(
            "lingshu.copilot.infra.skills.get_tenant_id",
            return_value="t1",
        ):
            result = await manager.register(
                mock_session,
                api_name="basic",
                display_name="Basic",
                system_prompt="Basic prompt",
            )
        assert result.description is None
        assert result.tool_bindings == []
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_get_skill_not_found(
        self, manager: SkillManager, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "lingshu.copilot.infra.skills.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.get("ri.skill.missing", mock_session)
        assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_skill_not_found(
        self, manager: SkillManager, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "lingshu.copilot.infra.skills.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.delete("ri.skill.missing", mock_session)
        assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND

    @pytest.mark.asyncio
    async def test_set_enabled(
        self, manager: SkillManager, mock_session: AsyncMock,
    ) -> None:
        """set_enabled delegates to update with the correct payload."""
        mock_skill = MagicMock()
        mock_skill.rid = "ri.skill.abc"
        mock_skill.enabled = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_skill)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "lingshu.copilot.infra.skills.get_tenant_id",
            return_value="t1",
        ):
            result = await manager.set_enabled("ri.skill.abc", False, mock_session)
        assert result.rid == "ri.skill.abc"
