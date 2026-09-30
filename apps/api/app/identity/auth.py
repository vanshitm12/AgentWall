import hashlib
import secrets

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.redis import get_redis

API_KEY_PREFIX = "aw_"
API_KEY_LENGTH = 48


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(API_KEY_LENGTH)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_api_key_prefix(api_key: str) -> str:
    return api_key[:12]


async def authenticate_agent(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Agent:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    api_key = auth_header.removeprefix("Bearer ").strip()
    key_hash = hash_api_key(api_key)

    result = await db.execute(select(Agent).where(Agent.api_key_hash == key_hash))
    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if agent.status == "KILLED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent has been killed",
        )

    if agent.status == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is suspended",
        )

    return agent


async def get_agent_from_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Agent:
    session_id = request.headers.get("Mcp-Session-Id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Mcp-Session-Id header",
        )

    redis = await get_redis()
    agent_id = await redis.get(f"session:{session_id}")

    if agent_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent not found for session",
        )

    if agent.status in ("KILLED", "SUSPENDED"):
        await redis.delete(f"session:{session_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent is {agent.status.lower()}",
        )

    return agent
