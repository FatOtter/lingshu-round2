"""MCP Protocol unit tests.

Tests JSON-RPC discovery for stdio/SSE transports, connection testing,
and error handling for the MCP manager.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.infra.mcp import McpManager, _parse_transport
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def manager() -> McpManager:
    return McpManager()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    return session


def _mock_conn(
    rid: str = "ri.mcp.1",
    transport: dict | None = None,
    tools: list | None = None,
    auth: dict | None = None,
) -> MagicMock:
    conn = MagicMock()
    conn.rid = rid
    conn.transport = transport or {"type": "stdio", "command": "mcp-server"}
    conn.discovered_tools = tools or []
    conn.status = "disconnected"
    conn.auth = auth
    return conn


def _wrap_result(value: MagicMock | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


class TestDiscoverStdio:
    async def test_discover_stdio_success(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        """Mock subprocess with valid JSON-RPC response."""
        conn = _mock_conn(transport={"type": "stdio", "command": "echo"})
        mock_session.execute = AsyncMock(return_value=_wrap_result(conn))

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_stdio_jsonrpc",
                return_value={"tools": [{"name": "read_file", "description": "Read a file"}]},
            ),
        ):
            tools = await manager.discover_tools("ri.mcp.1", mock_session)

        assert len(tools) == 1
        assert tools[0]["name"] == "read_file"

    async def test_discover_stdio_timeout(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        """Subprocess hangs, verify TimeoutError raised."""
        conn = _mock_conn(transport={"type": "stdio", "command": "echo"})
        mock_session.execute = AsyncMock(return_value=_wrap_result(conn))

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_stdio_jsonrpc",
                side_effect=AppError(
                    code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
                    message="MCP stdio request timed out after 30.0s",
                ),
            ),
            pytest.raises(AppError, match="timed out"),
        ):
            await manager.discover_tools("ri.mcp.1", mock_session)

    async def test_discover_stdio_invalid_json(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        """Invalid response, verify error handling."""
        conn = _mock_conn(transport={"type": "stdio", "command": "echo"})
        mock_session.execute = AsyncMock(return_value=_wrap_result(conn))

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_stdio_jsonrpc",
                side_effect=AppError(
                    code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
                    message="Invalid JSON response from MCP server",
                ),
            ),
            pytest.raises(AppError, match="Invalid JSON"),
        ):
            await manager.discover_tools("ri.mcp.1", mock_session)


class TestDiscoverSSE:
    async def test_discover_sse_success(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        """Mock httpx with valid SSE response."""
        conn = _mock_conn(
            transport={"type": "sse", "url": "http://mcp.local/sse"},
            auth=None,
        )
        mock_session.execute = AsyncMock(return_value=_wrap_result(conn))

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_http_jsonrpc",
                return_value={"tools": [{"name": "sse_tool", "description": "SSE tool"}]},
            ),
        ):
            tools = await manager.discover_tools("ri.mcp.1", mock_session)

        assert len(tools) == 1
        assert tools[0]["name"] == "sse_tool"

    async def test_discover_sse_auth_header(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        """Verify bearer token sent in auth config."""
        with patch(
            "lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1",
        ):
            result = await manager.connect(
                mock_session,
                api_name="sse-mcp",
                display_name="SSE MCP",
                transport={"type": "sse", "url": "http://mcp.local/sse"},
                auth={"type": "bearer", "token": "secret-token"},
            )

        assert result.auth is not None
        assert result.auth["token"] == "secret-token"


class TestTestConnection:
    async def test_test_connection_stdio(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        """Mock initialize response, verify server info returned."""
        conn = _mock_conn(transport={"type": "stdio", "command": "echo"})
        mock_session.execute = AsyncMock(return_value=_wrap_result(conn))

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_stdio_jsonrpc",
                return_value={
                    "serverInfo": {"name": "test", "version": "0.1"},
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                },
            ),
        ):
            result = await manager.test_connection("ri.mcp.1", mock_session)

        assert result["rid"] == "ri.mcp.1"
        assert result["status"] == "connected"
        assert result["server_name"] == "test"

    async def test_test_connection_sse(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        """Mock HTTP initialize for SSE transport."""
        conn = _mock_conn(transport={"type": "sse", "url": "http://mcp.local/sse"})
        mock_session.execute = AsyncMock(return_value=_wrap_result(conn))

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_http_jsonrpc",
                return_value={
                    "serverInfo": {"name": "sse-server", "version": "1.0"},
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": True},
                },
            ),
        ):
            result = await manager.test_connection("ri.mcp.1", mock_session)

        assert result["rid"] == "ri.mcp.1"
        assert result["status"] == "connected"
        assert result["server_name"] == "sse-server"

    async def test_test_connection_error(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        """Network error — connection not found raises AppError."""
        mock_session.execute = AsyncMock(return_value=_wrap_result(None))

        with (
            patch(
                "lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.test_connection("ri.mcp.missing", mock_session)

        assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND
