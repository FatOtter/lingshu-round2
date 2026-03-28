"""BS-13: MCP Tool Integration scenario tests.

Tests the lifecycle of MCP connections: register, test connection,
discover tools, verify agent integration, and SSE transport.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.copilot.agent.graph import AgentGraph
from lingshu.copilot.agent.state import CopilotState, SessionContext
from lingshu.copilot.infra.mcp import McpManager


@pytest.fixture
def manager() -> McpManager:
    return McpManager()


class TestBS13McpIntegration:
    """MCP Tool Integration: register -> test -> discover -> agent loads tools."""

    async def test_step1_register_mcp_connection(
        self, manager: McpManager, mock_db_session: AsyncMock,
    ) -> None:
        """Register MCP with stdio transport config."""
        result = await manager.connect(
            mock_db_session,
            api_name="code-tools",
            display_name="Code Tools MCP",
            description="Provides code analysis tools",
            transport={"type": "stdio", "command": "npx", "args": ["-y", "mcp-server-code"]},
            auth=None,
        )

        assert result.rid.startswith("ri.mcp.")
        assert result.api_name == "code-tools"
        assert result.transport["type"] == "stdio"
        assert result.transport["command"] == "npx"
        assert result.status == "disconnected"
        assert result.discovered_tools == []
        assert result.enabled is True
        mock_db_session.add.assert_called_once()

    async def test_step2_test_connection_success(
        self, manager: McpManager, mock_db_session: AsyncMock,
    ) -> None:
        """Mock subprocess, verify test_connection returns status dict."""
        mock_conn = MagicMock()
        mock_conn.rid = "ri.mcp.stdio1"
        mock_conn.transport = {"type": "stdio", "command": "echo"}
        mock_conn.auth = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_conn)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_jsonrpc_result = {
            "serverInfo": {"name": "test-server", "version": "1.0"},
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": True},
        }
        with patch(
            "lingshu.copilot.infra.mcp._send_stdio_jsonrpc",
            return_value=mock_jsonrpc_result,
        ):
            result = await manager.test_connection("ri.mcp.stdio1", mock_db_session)

        assert result["rid"] == "ri.mcp.stdio1"
        assert result["status"] == "connected"
        assert result["server_name"] == "test-server"

    async def test_step3_discover_tools(
        self, manager: McpManager, mock_db_session: AsyncMock,
    ) -> None:
        """Discover tools from MCP server, verify tools list returned."""
        mock_conn = MagicMock()
        mock_conn.rid = "ri.mcp.stdio1"
        mock_conn.transport = {"type": "stdio", "command": "echo"}
        mock_conn.auth = None
        mock_conn.discovered_tools = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_conn)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        discovered_tools = [
            {"name": "analyze_code", "description": "Analyze source code"},
            {"name": "lint_file", "description": "Run linter on file"},
        ]
        with patch(
            "lingshu.copilot.infra.mcp._send_stdio_jsonrpc",
            return_value={"tools": discovered_tools},
        ):
            tools = await manager.discover_tools("ri.mcp.stdio1", mock_db_session)

        assert len(tools) == 2
        assert tools[0]["name"] == "analyze_code"
        assert tools[1]["name"] == "lint_file"

    async def test_step4_discover_tools_timeout(
        self, manager: McpManager, mock_db_session: AsyncMock,
    ) -> None:
        """Simulate timeout via AppError, verify error status."""
        mock_conn = MagicMock()
        mock_conn.rid = "ri.mcp.timeout1"
        mock_conn.transport = {"type": "stdio", "command": "slow-server"}
        mock_conn.auth = None
        mock_conn.discovered_tools = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_conn)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        from lingshu.infra.errors import AppError, ErrorCode

        with (
            patch(
                "lingshu.copilot.infra.mcp._send_stdio_jsonrpc",
                side_effect=AppError(
                    code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
                    message="MCP stdio request timed out after 30.0s",
                ),
            ),
            pytest.raises(AppError, match="timed out"),
        ):
            await manager.discover_tools("ri.mcp.timeout1", mock_db_session)

    async def test_step5_agent_loads_mcp_tools(
        self, mock_db_session: AsyncMock,
    ) -> None:
        """Verify MCP tools appear in agent's available context (via subagent tools path)."""
        graph = AgentGraph()

        mock_agent = MagicMock()
        mock_agent.enabled = True
        mock_agent.api_name = "mcp_code_tools"
        mock_agent.display_name = "MCP Code Tools"
        mock_agent.description = "Code analysis via MCP"
        mock_agent.rid = "ri.subagent.mcp1"
        mock_agent.model_rid = None
        mock_agent.system_prompt = "You analyze code."
        mock_agent.tool_bindings = [{"tool": "analyze_code"}]
        mock_agent.safety_policy = {}

        with patch.object(
            graph._subagent_manager,
            "query",
            return_value=([mock_agent], 1),
        ):
            tools = await graph.get_subagent_tools(mock_db_session)

        assert len(tools) == 1
        assert tools[0]["name"] == "subagent_mcp_code_tools"
        assert tools[0]["metadata"]["tool_bindings"] == [{"tool": "analyze_code"}]

    async def test_step6_sse_transport(
        self, manager: McpManager, mock_db_session: AsyncMock,
    ) -> None:
        """Test SSE transport registration and discovery."""
        result = await manager.connect(
            mock_db_session,
            api_name="remote-mcp",
            display_name="Remote MCP Server",
            description="SSE-based remote MCP",
            transport={
                "type": "sse",
                "url": "http://mcp.example.com/sse",
                "headers": {"Authorization": "Bearer test-token"},
            },
            auth={"type": "bearer", "token": "test-token"},
        )

        assert result.rid.startswith("ri.mcp.")
        assert result.transport["type"] == "sse"
        assert result.transport["url"] == "http://mcp.example.com/sse"
        assert result.auth is not None
        assert result.auth["type"] == "bearer"
