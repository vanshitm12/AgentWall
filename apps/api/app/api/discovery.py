"""Tool discovery endpoint.

Connects to all registered downstream MCP servers,
discovers their tools, and stores them in the tool registry.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.mcp.downstream import downstream_manager
from app.models.mcp_server import MCPServer
from app.models.tool import Tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/scan")
async def scan_servers(db: AsyncSession = Depends(get_db)):
    """Connect to all registered MCP servers and discover their tools."""
    result = await db.execute(
        select(MCPServer).where(MCPServer.status == "ACTIVE")
    )
    servers = result.scalars().all()

    if not servers:
        return {"message": "No active servers registered", "connected": 0, "tools": 0}

    connected = 0
    total_tools = 0
    errors = []

    for server in servers:
        success = await downstream_manager.connect_server(
            server_id=server.id,
            name=server.name,
            endpoint=server.endpoint,
            transport_type=server.transport_type,
        )

        if success:
            connected += 1
            ds = downstream_manager._servers.get(server.id)
            if ds:
                for mcp_tool in ds.tools:
                    prefixed_name = f"{server.name}.{mcp_tool.name}"

                    existing = await db.execute(
                        select(Tool).where(
                            Tool.server_id == server.id, Tool.name == prefixed_name
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    tool = Tool(
                        server_id=server.id,
                        name=prefixed_name,
                        description=mcp_tool.description,
                        input_schema=(
                            mcp_tool.inputSchema if mcp_tool.inputSchema else None
                        ),
                    )
                    db.add(tool)
                    total_tools += 1
        else:
            ds = downstream_manager._servers.get(server.id)
            errors.append(
                {"server": server.name, "error": ds.error if ds else "Unknown error"}
            )

    await db.commit()

    return {
        "message": f"Scan complete. Connected to {connected}/{len(servers)} servers.",
        "connected": connected,
        "tools_discovered": total_tools,
        "errors": errors,
    }


@router.get("/status")
async def discovery_status():
    """Show current downstream connection status."""
    servers = []
    for sid, server in downstream_manager._servers.items():
        servers.append(
            {
                "server_id": sid,
                "name": server.name,
                "endpoint": server.endpoint,
                "transport_type": server.transport_type,
                "connected": server.connected,
                "tool_count": len(server.tools),
                "error": server.error,
            }
        )

    return {
        "connected_servers": downstream_manager.connected_count,
        "total_tools": downstream_manager.total_tool_count,
        "servers": servers,
    }
