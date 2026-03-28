"""BS-14: Multi-Model Switch scenario tests.

Tests model registration, default setting, session model resolution,
and fallback behavior when API key is missing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.agent.state import CopilotState, SessionContext
from lingshu.copilot.infra.models import ModelManager


@pytest.fixture
def model_manager() -> ModelManager:
    return ModelManager()


class TestBS14MultiModel:
    """Multi-Model Switch: register models, set default, fallback."""

    async def test_step1_register_gemini_model(
        self, model_manager: ModelManager, mock_db_session: AsyncMock,
    ) -> None:
        """Create model with provider='gemini'."""
        result = await model_manager.register(
            mock_db_session,
            api_name="gemini-flash",
            display_name="Gemini 2.0 Flash",
            provider="gemini",
            connection={"api_key_env": "GEMINI_API_KEY"},
            parameters={"temperature": 0.7, "max_tokens": 4096},
            is_default=False,
        )

        assert result.rid.startswith("ri.model.")
        assert result.api_name == "gemini-flash"
        assert result.provider == "gemini"
        assert result.connection == {"api_key_env": "GEMINI_API_KEY"}
        assert result.parameters["temperature"] == 0.7
        assert result.is_default is False

    async def test_step2_set_default_model(
        self, model_manager: ModelManager, mock_db_session: AsyncMock,
    ) -> None:
        """Register model as default, verify is_default=True."""
        result = await model_manager.register(
            mock_db_session,
            api_name="gemini-pro",
            display_name="Gemini Pro",
            provider="gemini",
            connection={"api_key_env": "GEMINI_API_KEY"},
            is_default=True,
        )

        assert result.is_default is True
        # Verify that existing defaults were cleared (update was called)
        mock_db_session.execute.assert_awaited()

    async def test_step3_create_session_uses_default(
        self, model_manager: ModelManager, mock_db_session: AsyncMock,
    ) -> None:
        """Verify get_default returns a model when one exists."""
        mock_model = MagicMock()
        mock_model.rid = "ri.model.default1"
        mock_model.is_default = True
        mock_model.provider = "gemini"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_model)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        default = await model_manager.get_default(mock_db_session)

        assert default is not None
        assert default.rid == "ri.model.default1"
        assert default.is_default is True

    async def test_step4_register_openai_model(
        self, model_manager: ModelManager, mock_db_session: AsyncMock,
    ) -> None:
        """Create OpenAI model config."""
        result = await model_manager.register(
            mock_db_session,
            api_name="gpt-4o",
            display_name="GPT-4o",
            provider="openai",
            connection={"api_key_env": "OPENAI_API_KEY", "base_url": "https://api.openai.com/v1"},
            parameters={"temperature": 0.5},
        )

        assert result.provider == "openai"
        assert result.api_name == "gpt-4o"
        assert result.connection["base_url"] == "https://api.openai.com/v1"

    async def test_step5_fallback_without_api_key(self) -> None:
        """No API key leads to structured fallback message with guidance."""
        graph = AgentGraph(gemini_api_key="")

        state = CopilotState(
            messages=[],
            context=SessionContext(mode="agent"),
        )
        events = await graph.process_message(state, "Analyze this data")

        assert len(events) == 2
        text_event = events[0]
        assert text_event["type"] == "text_delta"
        # Fallback mentions setup steps and providers
        assert "configure a model provider" in text_event["content"]
        assert "Gemini" in text_event["content"]
        assert events[1]["type"] == "done"
