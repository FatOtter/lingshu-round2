"""Unit tests for McpManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.infra.mcp import McpManager
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
    return session


class TestMcpManager:
    @pytest.mark.asyncio
    async def test_connect(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        with patch(
            "lingshu.copilot.infra.mcp.get_tenant_id",
            return_value="t1",
        ):
            result = await manager.connect(
                mock_session,
                api_name="my-mcp",
                display_name="My MCP Server",
                description="Test MCP server",
                transport={"type": "stdio", "command": "mcp-server"},
                auth={"token": "abc"},
            )
        assert result.rid.startswith("ri.mcp.")
        assert result.api_name == "my-mcp"
        assert result.display_name == "My MCP Server"
        assert result.description == "Test MCP server"
        assert result.transport == {"type": "stdio", "command": "mcp-server"}
        assert result.auth == {"token": "abc"}
        assert result.discovered_tools == []
        assert result.status == "disconnected"
        assert result.enabled is True
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_defaults(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        with patch(
            "lingshu.copilot.infra.mcp.get_tenant_id",
            return_value="t1",
        ):
            result = await manager.connect(
                mock_session,
                api_name="basic-mcp",
                display_name="Basic",
                transport={"type": "sse", "url": "http://localhost:3000"},
            )
        assert result.description is None
        assert result.auth is None

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "lingshu.copilot.infra.mcp.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.get("ri.mcp.missing", mock_session)
        assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "lingshu.copilot.infra.mcp.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await manager.delete("ri.mcp.missing", mock_session)
        assert exc_info.value.code == ErrorCode.COMMON_NOT_FOUND

    @pytest.mark.asyncio
    async def test_discover_tools_via_http(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.rid = "ri.mcp.abc"
        mock_conn.transport = {"type": "sse", "url": "http://localhost:8080/sse"}
        mock_conn.auth = None
        mock_conn.discovered_tools = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_conn)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_http_jsonrpc",
                return_value={"tools": [{"name": "tool1"}]},
            ),
        ):
            tools = await manager.discover_tools("ri.mcp.abc", mock_session)
        assert tools == [{"name": "tool1"}]

    @pytest.mark.asyncio
    async def test_discover_tools_empty_via_http(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.rid = "ri.mcp.abc"
        mock_conn.transport = {"type": "http", "url": "http://localhost:8080/mcp"}
        mock_conn.auth = None
        mock_conn.discovered_tools = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_conn)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_http_jsonrpc",
                return_value={"tools": []},
            ),
        ):
            tools = await manager.discover_tools("ri.mcp.abc", mock_session)
        assert tools == []

    @pytest.mark.asyncio
    async def test_test_connection_success(
        self, manager: McpManager, mock_session: AsyncMock,
    ) -> None:
        mock_conn = MagicMock()
        mock_conn.rid = "ri.mcp.abc"
        mock_conn.transport = {"type": "sse", "url": "http://localhost:8080/sse"}
        mock_conn.auth = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_conn)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("lingshu.copilot.infra.mcp.get_tenant_id", return_value="t1"),
            patch(
                "lingshu.copilot.infra.mcp._send_http_jsonrpc",
                return_value={
                    "serverInfo": {"name": "test-server", "version": "1.0"},
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                },
            ),
        ):
            result = await manager.test_connection("ri.mcp.abc", mock_session)
        assert result["rid"] == "ri.mcp.abc"
        assert result["status"] == "connected"
        assert result["server_name"] == "test-server"
        assert result["server_version"] == "1.0"
