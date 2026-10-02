import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.mcp.downstream import downstream_manager
from app.models.mcp_server import MCPServer
from app.models.tool import Tool
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerHealthResponse,
    MCPServerResponse,
    MCPServerUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/servers", tags=["servers"])


@router.post("", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(body: MCPServerCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(MCPServer).where(MCPServer.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Server name already exists")

    server = MCPServer(
        name=body.name,
        endpoint=body.endpoint,
        transport_type=body.transport_type,
        trust_level=body.trust_level,
        metadata_=body.metadata,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    return _to_response(server)


@router.get("", response_model=list[MCPServerResponse])
async def list_servers(
    status_filter: str | None = Query(default=None, alias="status"),
    trust_level: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(MCPServer).order_by(MCPServer.created_at.desc())
    if status_filter:
        query = query.where(MCPServer.status == status_filter)
    if trust_level:
        query = query.where(MCPServer.trust_level == trust_level)
    result = await db.execute(query)
    servers = result.scalars().all()
    return [_to_response(s) for s in servers]


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_server(server_id: str, db: AsyncSession = Depends(get_db)):
    server = await _get_or_404(server_id, db)
    return _to_response(server)


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def update_server(
    server_id: str, body: MCPServerUpdate, db: AsyncSession = Depends(get_db)
):
    server = await _get_or_404(server_id, db)

    if body.name is not None:
        server.name = body.name
    if body.endpoint is not None:
        server.endpoint = body.endpoint
    if body.transport_type is not None:
        server.transport_type = body.transport_type
    if body.status is not None:
        server.status = body.status
    if body.trust_level is not None:
        server.trust_level = body.trust_level
    if body.metadata is not None:
        server.metadata_ = body.metadata

    await db.commit()
    await db.refresh(server)

    return _to_response(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(server_id: str, db: AsyncSession = Depends(get_db)):
    server = await _get_or_404(server_id, db)
    await downstream_manager.disconnect_server(server_id)
    await db.execute(sa_delete(Tool).where(Tool.server_id == server_id))
    await db.delete(server)
    await db.commit()


@router.post("/{server_id}/health", response_model=MCPServerHealthResponse)
async def check_server_health(server_id: str, db: AsyncSession = Depends(get_db)):
    server = await _get_or_404(server_id, db)

    ds = downstream_manager._servers.get(server_id)
    if ds and ds.connected:
        return MCPServerHealthResponse(
            id=server.id,
            name=server.name,
            endpoint=server.endpoint,
            reachable=True,
            tool_count=len(ds.tools),
        )

    success = await downstream_manager.connect_server(
        server_id=server.id,
        name=server.name,
        endpoint=server.endpoint,
        transport_type=server.transport_type,
    )
    ds = downstream_manager._servers.get(server_id)
    return MCPServerHealthResponse(
        id=server.id,
        name=server.name,
        endpoint=server.endpoint,
        reachable=success,
        tool_count=len(ds.tools) if ds else 0,
        error=ds.error if ds and not success else None,
    )


@router.post("/{server_id}/scan")
async def scan_single_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Connect to a single MCP server, discover tools, and sync the registry."""
    server = await _get_or_404(server_id, db)

    success = await downstream_manager.connect_server(
        server_id=server.id,
        name=server.name,
        endpoint=server.endpoint,
        transport_type=server.transport_type,
    )
    if not success:
        ds = downstream_manager._servers.get(server_id)
        raise HTTPException(
            status_code=502,
            detail=f"Cannot connect to {server.name}: {ds.error if ds else 'Unknown error'}",
        )

    ds = downstream_manager._servers.get(server_id)
    if not ds:
        raise HTTPException(status_code=502, detail="Server state unavailable")

    discovered_names = {f"{server.name}.{t.name}" for t in ds.tools}

    existing_result = await db.execute(
        select(Tool).where(Tool.server_id == server_id)
    )
    existing_tools = {t.name: t for t in existing_result.scalars().all()}

    added = 0
    removed = 0
    unchanged = 0

    for mcp_tool in ds.tools:
        prefixed_name = f"{server.name}.{mcp_tool.name}"
        if prefixed_name in existing_tools:
            unchanged += 1
        else:
            tool = Tool(
                server_id=server.id,
                name=prefixed_name,
                description=mcp_tool.description,
                input_schema=mcp_tool.input_schema if mcp_tool.input_schema else None,
            )
            db.add(tool)
            added += 1

    for name, tool in existing_tools.items():
        if name not in discovered_names:
            await db.delete(tool)
            removed += 1

    await db.commit()

    return {
        "server": server.name,
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "total": len(discovered_names),
    }


def _to_response(server: MCPServer) -> MCPServerResponse:
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        endpoint=server.endpoint,
        transport_type=server.transport_type,
        status=server.status,
        trust_level=server.trust_level,
        metadata=server.metadata_,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


async def _get_or_404(server_id: str, db: AsyncSession) -> MCPServer:
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server
