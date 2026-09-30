"""MCP session manager.

Handles the two-layer identity model:
1. Agent authenticates with API key on first request
2. AgentWall creates a session in Redis and returns a session ID
3. All subsequent MCP requests use the session ID

Sessions are stored in Redis with a TTL. When an agent is killed,
its sessions are deleted from Redis, immediately blocking further requests.
"""

import logging
import secrets

from app.config import settings
from app.redis import redis_client

logger = logging.getLogger(__name__)

SESSION_PREFIX = "session:"


class SessionManager:
    def __init__(self) -> None:
        self.ttl = settings.session_ttl_seconds

    async def create(self, agent_id: str) -> str:
        session_id = "sess_" + secrets.token_urlsafe(32)
        key = SESSION_PREFIX + session_id
        await redis_client.set(key, agent_id, ex=self.ttl)
        logger.info("Session created: %s for agent %s", session_id, agent_id)
        return session_id

    async def get_agent_id(self, session_id: str) -> str | None:
        key = SESSION_PREFIX + session_id
        agent_id = await redis_client.get(key)
        if agent_id:
            await redis_client.expire(key, self.ttl)
        return agent_id

    async def destroy(self, session_id: str) -> None:
        key = SESSION_PREFIX + session_id
        await redis_client.delete(key)
        logger.info("Session destroyed: %s", session_id)

    async def destroy_all_for_agent(self, agent_id: str) -> int:
        destroyed = 0
        cursor: str | int = "0"
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor, match=f"{SESSION_PREFIX}*", count=100
            )
            for key in keys:
                stored_id = await redis_client.get(key)
                if stored_id == agent_id:
                    await redis_client.delete(key)
                    destroyed += 1
            if cursor == 0:
                break
        logger.info("Destroyed %d sessions for agent %s", destroyed, agent_id)
        return destroyed


session_manager = SessionManager()
