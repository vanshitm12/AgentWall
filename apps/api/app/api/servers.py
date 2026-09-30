from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mcp_server import MCPServer
from app.schemas.mcp_server import MCPServerCreate, MCPServerResponse, MCPServerUpdate

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


@router.get("", response_model=list[MCPServerResponse])
async def list_servers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MCPServer).order_by(MCPServer.created_at.desc()))
    servers = result.scalars().all()
    return [
        MCPServerResponse(
            id=s.id,
            name=s.name,
            endpoint=s.endpoint,
            transport_type=s.transport_type,
            status=s.status,
            trust_level=s.trust_level,
            metadata=s.metadata_,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in servers
    ]


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_server(server_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
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


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def update_server(
    server_id: str, body: MCPServerUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

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
