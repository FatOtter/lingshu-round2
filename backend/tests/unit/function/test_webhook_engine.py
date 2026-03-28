"""Unit tests for Webhook engine."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from lingshu.function.actions.engines.webhook import (
    WebhookEngine,
    _apply_response_mapping,
    _resolve_template_value,
)
from lingshu.infra.errors import AppError


@pytest.fixture
def engine() -> WebhookEngine:
    return WebhookEngine()


def _mock_response(
    json_data: dict | None = None,
    text: str = "",
    status_code: int = 200,
    content_type: str = "application/json",
) -> httpx.Response:
    """Build a fake httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        headers={"content-type": content_type},
        json=json_data,
        request=httpx.Request("GET", "http://test"),
    )
    return resp


class TestWebhookEngine:
    @pytest.mark.asyncio
    async def test_basic_get(self, engine: WebhookEngine) -> None:
        config = {
            "url": "https://api.example.com/status",
            "method": "GET",
        }
        mock_resp = _mock_response(json_data={"status": "ok"})

        with patch(
            "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await engine.execute(
                config, resolved_params={}, instances={},
            )

        assert result.data == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_post_with_body(self, engine: WebhookEngine) -> None:
        config = {
            "url": "https://api.example.com/commands",
            "method": "POST",
            "body_template": {
                "robot_id": "{{params.robot_id}}",
                "action": "start",
            },
        }
        mock_resp = _mock_response(json_data={"result": "accepted"})

        with patch(
            "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await engine.execute(
                config,
                resolved_params={"robot_id": "r123"},
                instances={},
            )

            # Verify the body was resolved
            call_kwargs = mock_client.request.call_args
            assert call_kwargs.kwargs["json"]["robot_id"] == "r123"
            assert call_kwargs.kwargs["json"]["action"] == "start"

        assert result.data == {"result": "accepted"}

    @pytest.mark.asyncio
    async def test_response_mapping(self, engine: WebhookEngine) -> None:
        config = {
            "url": "https://api.example.com/data",
            "method": "GET",
            "response_mapping": {
                "result_status": "$.status",
                "nested_val": "$.data.value",
            },
        }
        mock_resp = _mock_response(
            json_data={"status": "ok", "data": {"value": 42}},
        )

        with patch(
            "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await engine.execute(
                config, resolved_params={}, instances={},
            )

        assert result.computed_values["result_status"] == "ok"
        assert result.computed_values["nested_val"] == 42

    @pytest.mark.asyncio
    async def test_missing_url_raises(self, engine: WebhookEngine) -> None:
        with pytest.raises(AppError, match="requires a 'url'"):
            await engine.execute({}, resolved_params={}, instances={})

    @pytest.mark.asyncio
    async def test_timeout_raises(self, engine: WebhookEngine) -> None:
        config = {
            "url": "https://api.example.com/slow",
            "method": "GET",
            "timeout_ms": 100,
        }

        with patch(
            "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.ReadTimeout("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AppError, match="timed out"):
                await engine.execute(
                    config, resolved_params={}, instances={},
                )

    @pytest.mark.asyncio
    async def test_http_error_raises(self, engine: WebhookEngine) -> None:
        config = {
            "url": "https://api.example.com/fail",
            "method": "GET",
        }

        error_resp = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("GET", "https://api.example.com/fail"),
        )

        with patch(
            "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.HTTPStatusError(
                "Server Error",
                request=error_resp.request,
                response=error_resp,
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AppError, match="HTTP 500"):
                await engine.execute(
                    config, resolved_params={}, instances={},
                )

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, engine: WebhookEngine) -> None:
        config = {
            "url": "https://api.example.com/flaky",
            "method": "GET",
            "retry": {"max_attempts": 3, "backoff_ms": 10},
        }

        mock_resp = _mock_response(json_data={"ok": True})
        timeout_err = httpx.ReadTimeout("timeout")

        with patch(
            "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            # Fail twice, succeed on third
            mock_client.request.side_effect = [
                timeout_err, timeout_err, mock_resp,
            ]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await engine.execute(
                config, resolved_params={}, instances={},
            )

        assert result.data == {"ok": True}
        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, engine: WebhookEngine) -> None:
        config = {
            "url": "https://api.example.com/down",
            "method": "GET",
            "retry": {"max_attempts": 2, "backoff_ms": 10},
        }

        with patch(
            "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.ReadTimeout("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(AppError, match="timed out"):
                await engine.execute(
                    config, resolved_params={}, instances={},
                )

            assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_secret_resolution(self, engine: WebhookEngine) -> None:
        config = {
            "url": "https://api.example.com/secure",
            "method": "GET",
            "headers": {"Authorization": "Bearer {{secret:api_key}}"},
        }
        mock_resp = _mock_response(json_data={"authed": True})

        with (
            patch.dict(
                "os.environ", {"LINGSHU_SECRET_API_KEY": "my-secret-token"},
            ),
            patch(
                "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
            ) as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await engine.execute(config, resolved_params={}, instances={})

            call_kwargs = mock_client.request.call_args
            assert call_kwargs.kwargs["headers"]["Authorization"] == (
                "Bearer my-secret-token"
            )

    @pytest.mark.asyncio
    async def test_url_placeholder_resolution(
        self, engine: WebhookEngine,
    ) -> None:
        config = {
            "url": "https://api.example.com/robots/{{params.robot_id}}/status",
            "method": "GET",
        }
        mock_resp = _mock_response(json_data={"status": "online"})

        with patch(
            "lingshu.function.actions.engines.webhook.httpx.AsyncClient",
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await engine.execute(
                config,
                resolved_params={"robot_id": "r456"},
                instances={},
            )

            call_kwargs = mock_client.request.call_args
            assert call_kwargs.kwargs["url"] == (
                "https://api.example.com/robots/r456/status"
            )


class TestResponseMapping:
    def test_simple_path(self) -> None:
        data = {"status": "ok", "count": 5}
        result = _apply_response_mapping(
            {"s": "$.status", "c": "$.count"}, data,
        )
        assert result == {"s": "ok", "c": 5}

    def test_nested_path(self) -> None:
        data = {"a": {"b": {"c": 99}}}
        result = _apply_response_mapping({"val": "$.a.b.c"}, data)
        assert result == {"val": 99}

    def test_missing_path(self) -> None:
        result = _apply_response_mapping({"val": "$.missing"}, {"x": 1})
        assert result == {"val": None}

    def test_empty_mapping(self) -> None:
        assert _apply_response_mapping({}, {"x": 1}) == {}


class TestTemplateValueResolution:
    def test_string_placeholder(self) -> None:
        result = _resolve_template_value(
            "{{params.name}}", {"name": "test"}, {},
        )
        assert result == "test"

    def test_dict_template(self) -> None:
        template = {"key": "{{params.val}}", "static": "hello"}
        result = _resolve_template_value(template, {"val": 42}, {})
        assert result == {"key": 42, "static": "hello"}

    def test_list_template(self) -> None:
        template = ["{{params.a}}", "{{params.b}}"]
        result = _resolve_template_value(
            template, {"a": "x", "b": "y"}, {},
        )
        assert result == ["x", "y"]
