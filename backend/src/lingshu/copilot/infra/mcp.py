"""MCP connection management: CRUD + real protocol discovery and testing."""

import asyncio
import json
import logging
from typing import Any

import httpx
from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.models import McpConnection
from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.rid import generate_rid

logger = logging.getLogger(__name__)

_DISCOVER_TIMEOUT = 30.0
_TEST_TIMEOUT = 10.0
_JSONRPC_VERSION = "2.0"


def _make_jsonrpc_request(method: str, request_id: int = 1) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request envelope."""
    return {
        "jsonrpc": _JSONRPC_VERSION,
        "id": request_id,
        "method": method,
        "params": {},
    }


async def _send_stdio_jsonrpc(
    command: list[str],
    method: str,
    timeout: float,
) -> dict[str, Any]:
    """Launch a subprocess and send a JSON-RPC request via stdin/stdout."""
    request = _make_jsonrpc_request(method)
    request_bytes = json.dumps(request).encode() + b"\n"

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"MCP command not found: {command[0]}",
            details={"command": command[0], "error": str(exc)},
        ) from exc
    except OSError as exc:
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"Failed to start MCP process: {exc}",
            details={"command": command, "error": str(exc)},
        ) from exc

    try:
        stdout_data, stderr_data = await asyncio.wait_for(
            process.communicate(input=request_bytes),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"MCP stdio request timed out after {timeout}s",
            details={"command": command, "method": method},
        ) from exc

    if process.returncode != 0:
        stderr_text = stderr_data.decode(errors="replace").strip()
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"MCP process exited with code {process.returncode}",
            details={"stderr": stderr_text[:500], "command": command},
        )

    try:
        response = json.loads(stdout_data.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message="Invalid JSON response from MCP server",
            details={"raw_output": stdout_data.decode(errors="replace")[:500]},
        ) from exc

    if "error" in response:
        rpc_error = response["error"]
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"MCP JSON-RPC error: {rpc_error.get('message', 'unknown')}",
            details={"rpc_error": rpc_error},
        )

    return response.get("result", {})


async def _send_http_jsonrpc(
    url: str,
    method: str,
    timeout: float,
    auth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send JSON-RPC request via HTTP POST."""
    request = _make_jsonrpc_request(method)
    headers: dict[str, str] = {"Content-Type": "application/json"}

    if auth:
        auth_type = auth.get("type", "")
        if auth_type == "bearer":
            token = auth.get("token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "header":
            header_name = auth.get("header_name", "")
            header_value = auth.get("header_value", "")
            if header_name and header_value:
                headers[header_name] = header_value

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=request, headers=headers)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"MCP HTTP request timed out after {timeout}s",
            details={"url": url, "method": method},
        ) from exc
    except httpx.ConnectError as exc:
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"Cannot connect to MCP server at {url}",
            details={"url": url, "error": str(exc)},
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"MCP server returned HTTP {exc.response.status_code}",
            details={"url": url, "status_code": exc.response.status_code},
        ) from exc

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message="Invalid JSON response from MCP server",
            details={"url": url},
        ) from exc

    if "error" in body:
        rpc_error = body["error"]
        raise AppError(
            code=ErrorCode.COPILOT_MCP_CONNECTION_FAILED,
            message=f"MCP JSON-RPC error: {rpc_error.get('message', 'unknown')}",
            details={"rpc_error": rpc_error},
        )

    return body.get("result", {})


def _parse_transport(transport: dict[str, Any]) -> tuple[str, Any]:
    """Parse transport config and return (type, connection_info).

    Returns:
        ("stdio", ["command", "arg1", ...]) or ("http", "https://...")
    """
    transport_type = transport.get("type", "").lower()

    if transport_type == "stdio":
        command = transport.get("command", "")
        args = transport.get("args", [])
        if not command:
            raise AppError(
                code=ErrorCode.COMMON_INVALID_INPUT,
                message="stdio transport requires a 'command' field",
            )
        cmd_list = [command, *args] if args else [command]
        return "stdio", cmd_list

    if transport_type in ("sse", "http", "streamable-http"):
        url = transport.get("url", "")
        if not url:
            raise AppError(
                code=ErrorCode.COMMON_INVALID_INPUT,
                message=f"{transport_type} transport requires a 'url' field",
            )
        return "http", url

    raise AppError(
        code=ErrorCode.COMMON_INVALID_INPUT,
        message=f"Unsupported MCP transport type: {transport_type}. "
                "Supported: stdio, sse, http, streamable-http",
    )


class McpManager:
    """CRUD manager for MCP Connections."""

    async def connect(
        self,
        session: AsyncSession,
        *,
        api_name: str,
        display_name: str,
        description: str | None = None,
        transport: dict[str, Any],
        auth: dict[str, Any] | None = None,
    ) -> McpConnection:
        """Register a new MCP connection."""
        tenant_id = get_tenant_id()

        connection = McpConnection(
            rid=generate_rid("mcp"),
            tenant_id=tenant_id,
            api_name=api_name,
            display_name=display_name,
            description=description,
            transport=transport,
            auth=auth,
            discovered_tools=[],
            status="disconnected",
            enabled=True,
        )
        session.add(connection)
        await session.flush()
        await session.commit()
        return connection

    async def get(
        self, rid: str, session: AsyncSession,
    ) -> McpConnection:
        tenant_id = get_tenant_id()
        result = await session.execute(
            select(McpConnection).where(
                McpConnection.rid == rid,
                McpConnection.tenant_id == tenant_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message=f"MCP connection {rid} not found",
            )
        return conn

    async def update(
        self,
        rid: str,
        updates: dict[str, Any],
        session: AsyncSession,
    ) -> McpConnection:
        tenant_id = get_tenant_id()

        await session.execute(
            update(McpConnection)
            .where(
                McpConnection.rid == rid,
                McpConnection.tenant_id == tenant_id,
            )
            .values(**updates)
        )
        await session.flush()
        await session.commit()
        return await self.get(rid, session)

    async def delete(
        self, rid: str, session: AsyncSession,
    ) -> None:
        tenant_id = get_tenant_id()
        result = await session.execute(
            select(McpConnection).where(
                McpConnection.rid == rid,
                McpConnection.tenant_id == tenant_id,
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message=f"MCP connection {rid} not found",
            )
        await session.delete(conn)
        await session.commit()

    async def query(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[McpConnection], int]:
        tenant_id = get_tenant_id()
        base = select(McpConnection).where(
            McpConnection.tenant_id == tenant_id,
        )
        count_result = await session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await session.execute(
            base.order_by(McpConnection.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def discover_tools(
        self, rid: str, session: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Discover available tools from MCP server via JSON-RPC tools/list."""
        conn = await self.get(rid, session)

        try:
            transport_type, conn_info = _parse_transport(conn.transport)

            if transport_type == "stdio":
                result = await _send_stdio_jsonrpc(
                    conn_info, "tools/list", _DISCOVER_TIMEOUT,
                )
            else:
                result = await _send_http_jsonrpc(
                    conn_info, "tools/list", _DISCOVER_TIMEOUT, conn.auth,
                )

            tools = result.get("tools", [])
            if not isinstance(tools, list):
                tools = []

            # Cache discovered tools and update status
            await self.update(
                rid,
                {"discovered_tools": tools, "status": "connected"},
                session,
            )

            return tools

        except AppError:
            # Update status to error, then re-raise
            try:
                await self.update(rid, {"status": "error"}, session)
            except Exception:
                logger.warning("Failed to update MCP status to error for %s", rid)
            raise
        except Exception as exc:
            logger.exception("Unexpected error discovering tools for %s", rid)
            try:
                await self.update(rid, {"status": "error"}, session)
            except Exception:
                logger.warning("Failed to update MCP status to error for %s", rid)
            raise AppError(
                code=ErrorCode.COPILOT_MCP_DISCOVERY_FAILED,
                message=f"Tool discovery failed: {exc}",
                details={"rid": rid},
            ) from exc

    async def test_connection(
        self, rid: str, session: AsyncSession,
    ) -> dict[str, Any]:
        """Test MCP server connectivity via JSON-RPC initialize request."""
        conn = await self.get(rid, session)

        try:
            transport_type, conn_info = _parse_transport(conn.transport)

            if transport_type == "stdio":
                result = await _send_stdio_jsonrpc(
                    conn_info, "initialize", _TEST_TIMEOUT,
                )
            else:
                result = await _send_http_jsonrpc(
                    conn_info, "initialize", _TEST_TIMEOUT, conn.auth,
                )

            server_info = result.get("serverInfo", {})

            return {
                "rid": conn.rid,
                "status": "connected",
                "server_name": server_info.get("name", "unknown"),
                "server_version": server_info.get("version", "unknown"),
                "protocol_version": result.get("protocolVersion", "unknown"),
                "capabilities": result.get("capabilities", {}),
            }

        except AppError as exc:
            return {
                "rid": conn.rid,
                "status": "error",
                "message": exc.message,
                "details": exc.details,
            }
        except Exception as exc:
            logger.exception("Unexpected error testing MCP connection %s", rid)
            return {
                "rid": conn.rid,
                "status": "error",
                "message": f"Connection test failed: {exc}",
            }
