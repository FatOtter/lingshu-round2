"""Webhook engine: external HTTP calls with retry and response mapping."""

import asyncio
import os
import re
from typing import Any

import httpx

from lingshu.function.actions.engines.base import EngineResult
from lingshu.infra.context import get_user_id
from lingshu.infra.errors import AppError, ErrorCode

_PLACEHOLDER_PATTERN = re.compile(r"\{\{(.+?)\}\}")

DEFAULT_TIMEOUT_MS = 5000
DEFAULT_MAX_ATTEMPTS = 1
DEFAULT_BACKOFF_MS = 1000


class WebhookEngine:
    """Execute external HTTP webhook calls."""

    async def execute(
        self,
        config: dict[str, Any],
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> EngineResult:
        """Perform an HTTP request based on config.

        config keys:
          - url: str
          - method: str (GET, POST, PUT, DELETE)
          - headers: dict[str, str] (optional)
          - body_template: dict | str (optional)
          - timeout_ms: int (default 5000)
          - retry: {max_attempts: int, backoff_ms: int} (optional)
          - response_mapping: dict[str, str] (optional, dot-path navigation)
        """
        url = config.get("url")
        if not url:
            raise AppError(
                code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                message="Webhook engine requires a 'url' in config",
            )

        method = config.get("method", "GET").upper()
        headers_template = config.get("headers", {})
        body_template = config.get("body_template")
        timeout_ms = config.get("timeout_ms", DEFAULT_TIMEOUT_MS)
        retry_config = config.get("retry", {})
        response_mapping = config.get("response_mapping", {})

        max_attempts = retry_config.get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        backoff_ms = retry_config.get("backoff_ms", DEFAULT_BACKOFF_MS)

        # Resolve placeholders in url, headers, body
        resolved_url = _resolve_template_string(
            url, resolved_params, instances,
        )
        resolved_headers = {
            k: _resolve_template_string(v, resolved_params, instances)
            for k, v in headers_template.items()
        }
        resolved_body: Any = None
        if body_template is not None:
            resolved_body = _resolve_template_value(
                body_template, resolved_params, instances,
            )

        timeout_sec = timeout_ms / 1000.0

        last_error: Exception | None = None
        for attempt in range(max_attempts):
            if attempt > 0:
                await asyncio.sleep(backoff_ms * (2 ** (attempt - 1)) / 1000.0)

            try:
                response_data = await _make_request(
                    method=method,
                    url=resolved_url,
                    headers=resolved_headers,
                    body=resolved_body,
                    timeout=timeout_sec,
                )

                # Apply response mapping
                computed = _apply_response_mapping(
                    response_mapping, response_data,
                )

                return EngineResult(
                    data=response_data,
                    computed_values=computed,
                )
            except httpx.TimeoutException:
                last_error = AppError(
                    code=ErrorCode.FUNCTION_TIMEOUT,
                    message=f"Webhook timed out after {timeout_ms}ms",
                )
            except httpx.HTTPStatusError as exc:
                last_error = AppError(
                    code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                    message=f"Webhook returned HTTP {exc.response.status_code}",
                    details={"response_body": exc.response.text[:500]},
                )
            except httpx.HTTPError as exc:
                last_error = AppError(
                    code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                    message=f"Webhook request failed: {exc}",
                )

        # All retries exhausted
        if isinstance(last_error, AppError):
            raise last_error
        raise AppError(
            code=ErrorCode.FUNCTION_EXECUTION_FAILED,
            message="Webhook request failed after retries",
        )


async def _make_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: Any,
    timeout: float,
) -> Any:
    """Execute the HTTP request and return parsed JSON or text."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=body if body is not None else None,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return {"text": response.text}


def _resolve_template_string(
    value: str,
    resolved_params: dict[str, Any],
    instances: dict[str, dict[str, Any]],
) -> str:
    """Replace ``{{...}}`` placeholders in a string."""

    def _replacer(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        resolved = _resolve_expression(expr, resolved_params, instances)
        if resolved is None:
            return match.group(0)
        return str(resolved)

    return _PLACEHOLDER_PATTERN.sub(_replacer, value)


def _resolve_template_value(
    value: Any,
    resolved_params: dict[str, Any],
    instances: dict[str, dict[str, Any]],
) -> Any:
    """Recursively resolve placeholders in a nested structure."""
    if isinstance(value, str):
        # If the entire string is a single placeholder, return the raw value
        match = _PLACEHOLDER_PATTERN.fullmatch(value)
        if match:
            resolved = _resolve_expression(
                match.group(1).strip(), resolved_params, instances,
            )
            return resolved if resolved is not None else value
        return _resolve_template_string(value, resolved_params, instances)

    if isinstance(value, dict):
        return {
            k: _resolve_template_value(v, resolved_params, instances)
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [
            _resolve_template_value(v, resolved_params, instances)
            for v in value
        ]

    return value


def _resolve_expression(
    expr: str,
    resolved_params: dict[str, Any],
    instances: dict[str, dict[str, Any]],
) -> Any:
    """Resolve a dotted expression.

    Supported forms:
      - ``params.param_name`` or ``params.param_name.field``
      - ``context.user_id``
      - ``secret:key_name`` → env var ``LINGSHU_SECRET_<KEY_NAME>``
      - bare ``param_name`` or ``param_name.field``
    """
    # Secret resolution
    if expr.startswith("secret:"):
        key_name = expr[len("secret:"):]
        env_key = f"LINGSHU_SECRET_{key_name.upper()}"
        return os.environ.get(env_key, "")

    # Context resolution
    if expr.startswith("context."):
        field = expr[len("context."):]
        if field == "user_id":
            try:
                return get_user_id()
            except RuntimeError:
                return None
        return None

    # Params resolution — strip leading "params." if present
    path = expr
    if path.startswith("params."):
        path = path[len("params."):]

    parts = path.split(".", 1)
    param_name = parts[0]

    if len(parts) == 2:
        field_name = parts[1]
        if param_name in instances:
            return instances[param_name].get(field_name)
        param_val = resolved_params.get(param_name)
        if isinstance(param_val, dict):
            return param_val.get(field_name)
        return None

    return resolved_params.get(param_name)


def _apply_response_mapping(
    mapping: dict[str, str],
    response_data: Any,
) -> dict[str, Any]:
    """Extract fields from response using simple dot-path navigation.

    Paths like ``$.status`` or ``status.code`` navigate into the response dict.
    """
    if not mapping or not isinstance(response_data, dict):
        return {}

    computed: dict[str, Any] = {}
    for output_name, path in mapping.items():
        computed[output_name] = _navigate_path(response_data, path)
    return computed


def _navigate_path(data: Any, path: str) -> Any:
    """Navigate a dot-separated path, stripping optional leading ``$``."""
    clean = path.lstrip("$").lstrip(".")
    if not clean:
        return data

    current = data
    for segment in clean.split("."):
        if isinstance(current, dict):
            current = current.get(segment)
        elif isinstance(current, list) and segment.isdigit():
            idx = int(segment)
            current = current[idx] if idx < len(current) else None
        else:
            return None
    return current
