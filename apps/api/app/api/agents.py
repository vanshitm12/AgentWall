from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.identity.auth import generate_api_key, get_api_key_prefix, hash_api_key
from app.models.agent import Agent
from app.redis import get_redis
from app.schemas.agent import (
    AgentCreate,
    AgentCreateResponse,
    AgentResponse,
    AgentStatusUpdate,
    AgentUpdate,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Agent).where(Agent.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent name already exists")

    api_key = generate_api_key()

    agent = Agent(
        name=body.name,
        description=body.description,
        api_key_hash=hash_api_key(api_key),
        api_key_prefix=get_api_key_prefix(api_key),
        metadata_=body.metadata,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return AgentCreateResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        api_key=api_key,
        api_key_prefix=agent.api_key_prefix,
        created_at=agent.created_at,
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    agents = result.scalars().all()
    return [
        AgentResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            status=a.status,
            api_key_prefix=a.api_key_prefix,
            metadata=a.metadata_,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in agents
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        api_key_prefix=agent.api_key_prefix,
        metadata=agent.metadata_,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str, body: AgentUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if body.name is not None:
        agent.name = body.name
    if body.description is not None:
        agent.description = body.description
    if body.status is not None:
        agent.status = body.status
    if body.metadata is not None:
        agent.metadata_ = body.metadata

    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        api_key_prefix=agent.api_key_prefix,
        metadata=agent.metadata_,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.post("/{agent_id}/status", response_model=AgentResponse)
async def update_agent_status(
    agent_id: str, body: AgentStatusUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.status = body.status

    if body.status in ("KILLED", "SUSPENDED"):
        redis = await get_redis()
        cursor = "0"
        while cursor != 0:
            cursor, keys = await redis.scan(
                cursor=cursor, match="session:*", count=100
            )
            for key in keys:
                stored_agent_id = await redis.get(key)
                if stored_agent_id == agent_id:
                    await redis.delete(key)
            if cursor == "0":
                break

    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        status=agent.status,
        api_key_prefix=agent.api_key_prefix,
        metadata=agent.metadata_,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )
