"""Downstream MCP server connection manager.

Manages persistent connections to registered downstream MCP servers.
Fetches tool listings and forwards tool calls.

Each downstream server runs as a separate MCP server (in Docker).
AgentWall connects to each one as an MCP client.
Tools are namespaced by server name: "github.read_file", "database.query".
"""

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, Tool as MCPTool

logger = logging.getLogger(__name__)


@dataclass
class DownstreamServer:
    server_id: str
    name: str
    endpoint: str
    transport_type: str
    session: ClientSession | None = None
    tools: list[MCPTool] = field(default_factory=list)
    connected: bool = False
    error: str | None = None


class DownstreamManager:
    """Manages connections to all registered downstream MCP servers."""

    def __init__(self) -> None:
        self._servers: dict[str, DownstreamServer] = {}
        self._exit_stack = AsyncExitStack()
        self._tool_to_server: dict[str, str] = {}

    async def connect_server(
        self, server_id: str, name: str, endpoint: str, transport_type: str
    ) -> bool:
        server = DownstreamServer(
            server_id=server_id,
            name=name,
            endpoint=endpoint,
            transport_type=transport_type,
        )

        try:
            if transport_type == "sse":
                read_stream, write_stream = await self._exit_stack.enter_async_context(
                    sse_client(endpoint + "/sse")
                )
            else:
                read_stream, write_stream = (
                    await self._exit_stack.enter_async_context(
                        streamable_http_client(endpoint + "/mcp")
                    )
                )

            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()

            server.session = session
            server.connected = True

            result = await session.list_tools()
            server.tools = list(result.tools)

            for tool in server.tools:
                prefixed = f"{name}.{tool.name}"
                self._tool_to_server[prefixed] = server_id

            self._servers[server_id] = server
            logger.info(
                "Connected to %s (%s) — %d tools discovered",
                name,
                endpoint,
                len(server.tools),
            )
            return True

        except Exception as e:
            server.error = str(e)
            server.connected = False
            self._servers[server_id] = server
            logger.error("Failed to connect to %s at %s: %s", name, endpoint, e)
            return False

    async def disconnect_all(self) -> None:
        await self._exit_stack.aclose()
        self._servers.clear()
        self._tool_to_server.clear()
        logger.info("All downstream connections closed")

    def list_all_tools(self) -> list[dict]:
        """Return all tools from all connected servers, prefixed by server name."""
        tools = []
        for server in self._servers.values():
            if not server.connected:
                continue
            for tool in server.tools:
                tools.append(
                    {
                        "name": f"{server.name}.{tool.name}",
                        "description": tool.description or "",
                        "inputSchema": (
                            tool.inputSchema if tool.inputSchema else {"type": "object"}
                        ),
                    }
                )
        return tools

    def resolve_tool(self, prefixed_name: str) -> tuple[str, str, DownstreamServer] | None:
        """Given a prefixed tool name, return (server_id, original_name, server)."""
        server_id = self._tool_to_server.get(prefixed_name)
        if not server_id:
            return None

        server = self._servers.get(server_id)
        if not server or not server.connected or not server.session:
            return None

        parts = prefixed_name.split(".", 1)
        if len(parts) != 2:
            return None

        original_name = parts[1]
        return server_id, original_name, server

    async def call_tool(
        self, prefixed_name: str, arguments: dict | None = None
    ) -> CallToolResult | None:
        """Forward a tool call to the correct downstream server."""
        resolved = self.resolve_tool(prefixed_name)
        if not resolved:
            return None

        server_id, original_name, server = resolved
        assert server.session is not None

        logger.info(
            "Forwarding %s → %s.%s", prefixed_name, server.name, original_name
        )
        result = await server.session.call_tool(original_name, arguments)
        return result

    def get_server_for_tool(self, prefixed_name: str) -> DownstreamServer | None:
        resolved = self.resolve_tool(prefixed_name)
        if not resolved:
            return None
        return resolved[2]

    @property
    def connected_count(self) -> int:
        return sum(1 for s in self._servers.values() if s.connected)

    @property
    def total_tool_count(self) -> int:
        return len(self._tool_to_server)


downstream_manager = DownstreamManager()
