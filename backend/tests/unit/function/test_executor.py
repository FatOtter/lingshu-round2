"""Tests for GlobalFunctionExecutor: dispatch by implementation type."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lingshu.function.globals.executor import GlobalFunctionExecutor
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def mock_builtins() -> AsyncMock:
    builtins = AsyncMock()
    return builtins


@pytest.fixture
def executor(mock_builtins: AsyncMock) -> GlobalFunctionExecutor:
    with patch("lingshu.function.globals.executor.PythonVenvEngine"):
        with patch("lingshu.function.globals.executor.WebhookEngine"):
            ex = GlobalFunctionExecutor(mock_builtins)
            ex._python_venv = AsyncMock()
            ex._webhook = AsyncMock()
            return ex


@pytest.mark.asyncio
async def test_execute_builtin(
    executor: GlobalFunctionExecutor, mock_builtins: AsyncMock
) -> None:
    """execute() should dispatch to builtins for type=builtin."""
    mock_builtins.execute.return_value = {"result": "ok"}

    result = await executor.execute(
        implementation={"type": "builtin", "handler": "query_instances"},
        params={"object_type_rid": "ri.obj.o1"},
        tenant_id="ri.tenant.t1",
    )

    assert result == {"result": "ok"}
    mock_builtins.execute.assert_awaited_once_with(
        "query_instances", {"object_type_rid": "ri.obj.o1"}, "ri.tenant.t1"
    )


@pytest.mark.asyncio
async def test_execute_python(executor: GlobalFunctionExecutor) -> None:
    """execute() should dispatch to PythonVenvEngine for type=python."""
    mock_result = MagicMock()
    mock_result.data = {"computed": 42}
    executor._python_venv.execute.return_value = mock_result

    result = await executor.execute(
        implementation={"type": "python", "script": "return 42", "timeout": 10},
        params={"x": 1},
        tenant_id="ri.tenant.t1",
    )

    assert result == {"computed": 42}
    executor._python_venv.execute.assert_awaited_once()
    call_args = executor._python_venv.execute.call_args
    config = call_args[0][0] if call_args[0] else call_args[1].get("config")
    assert config["script"] == "return 42"
    assert config["timeout"] == 10


@pytest.mark.asyncio
async def test_execute_python_default_timeout(
    executor: GlobalFunctionExecutor,
) -> None:
    """execute() should use default timeout=30 for python when not specified."""
    mock_result = MagicMock()
    mock_result.data = None
    executor._python_venv.execute.return_value = mock_result

    await executor.execute(
        implementation={"type": "python", "script": "pass"},
        params={},
        tenant_id="ri.tenant.t1",
    )

    call_args = executor._python_venv.execute.call_args
    config = call_args[0][0]
    assert config["timeout"] == 30


@pytest.mark.asyncio
async def test_execute_webhook(executor: GlobalFunctionExecutor) -> None:
    """execute() should dispatch to WebhookEngine for type=webhook."""
    mock_result = MagicMock()
    mock_result.data = {"status": "sent"}
    executor._webhook.execute.return_value = mock_result

    result = await executor.execute(
        implementation={
            "type": "webhook",
            "url": "https://example.com/hook",
            "method": "POST",
        },
        params={"payload": "data"},
        tenant_id="ri.tenant.t1",
    )

    assert result == {"status": "sent"}
    executor._webhook.execute.assert_awaited_once()
    call_args = executor._webhook.execute.call_args
    webhook_config = call_args[0][0]
    assert "url" in webhook_config
    assert "method" in webhook_config
    # "type" should be stripped from config
    assert "type" not in webhook_config


@pytest.mark.asyncio
async def test_execute_unknown_type_raises(
    executor: GlobalFunctionExecutor,
) -> None:
    """execute() should raise AppError for unknown implementation types."""
    with pytest.raises(AppError) as exc_info:
        await executor.execute(
            implementation={"type": "unknown_engine"},
            params={},
            tenant_id="ri.tenant.t1",
        )

    assert exc_info.value.code == ErrorCode.FUNCTION_EXECUTION_FAILED
    assert "unknown_engine" in exc_info.value.message


@pytest.mark.asyncio
async def test_execute_empty_type_raises(
    executor: GlobalFunctionExecutor,
) -> None:
    """execute() should raise AppError when type is missing."""
    with pytest.raises(AppError) as exc_info:
        await executor.execute(
            implementation={},
            params={},
            tenant_id="ri.tenant.t1",
        )

    assert exc_info.value.code == ErrorCode.FUNCTION_EXECUTION_FAILED


@pytest.mark.asyncio
async def test_execute_builtin_passes_correct_params(
    executor: GlobalFunctionExecutor, mock_builtins: AsyncMock
) -> None:
    """execute() should pass handler name and params to builtins correctly."""
    mock_builtins.execute.return_value = []

    await executor.execute(
        implementation={"type": "builtin", "handler": "list_object_types"},
        params={"limit": 10, "offset": 0},
        tenant_id="ri.tenant.t2",
    )

    mock_builtins.execute.assert_awaited_once_with(
        "list_object_types", {"limit": 10, "offset": 0}, "ri.tenant.t2"
    )
