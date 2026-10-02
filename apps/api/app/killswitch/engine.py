"""Kill switch engine.

Redis-based instant agent termination. Provides two levels:
1. Per-agent kill switch: blocks a specific agent immediately
2. Global kill switch: blocks ALL agents immediately

Both are checked in the proxy before any processing, making them
faster than DB status checks (Redis vs PostgreSQL round-trip).

Keys:
  killswitch:agent:{agent_id} → "1" (with optional TTL)
  killswitch:global → "1"
"""

import logging

from app.redis import redis_client

logger = logging.getLogger(__name__)

AGENT_KEY_PREFIX = "killswitch:agent:"
GLOBAL_KEY = "killswitch:global"


async def is_agent_killed(agent_id: str) -> bool:
    val = await redis_client.get(f"{AGENT_KEY_PREFIX}{agent_id}")
    return val is not None


async def is_global_killed() -> bool:
    val = await redis_client.get(GLOBAL_KEY)
    return val is not None


async def check_kill_switch(agent_id: str) -> str | None:
    """Check both global and per-agent kill switches.

    Returns None if no kill switch is active, or a reason string if blocked.
    """
    if await is_global_killed():
        return "Global kill switch is active — all agent access is suspended"
    if await is_agent_killed(agent_id):
        return f"Kill switch active for agent {agent_id}"
    return None


async def activate_agent(agent_id: str, reason: str = "") -> None:
    await redis_client.set(f"{AGENT_KEY_PREFIX}{agent_id}", reason or "1")
    logger.warning("KILL SWITCH ACTIVATED: agent=%s reason=%s", agent_id, reason)


async def deactivate_agent(agent_id: str) -> bool:
    result = await redis_client.delete(f"{AGENT_KEY_PREFIX}{agent_id}")
    if result:
        logger.info("Kill switch deactivated: agent=%s", agent_id)
    return bool(result)


async def activate_global(reason: str = "") -> None:
    await redis_client.set(GLOBAL_KEY, reason or "1")
    logger.critical("GLOBAL KILL SWITCH ACTIVATED: reason=%s", reason)


async def deactivate_global() -> bool:
    result = await redis_client.delete(GLOBAL_KEY)
    if result:
        logger.info("Global kill switch deactivated")
    return bool(result)


async def get_agent_status(agent_id: str) -> dict:
    val = await redis_client.get(f"{AGENT_KEY_PREFIX}{agent_id}")
    return {
        "agent_id": agent_id,
        "active": val is not None,
        "reason": val if val and val != "1" else None,
    }


async def get_global_status() -> dict:
    val = await redis_client.get(GLOBAL_KEY)
    return {
        "active": val is not None,
        "reason": val if val and val != "1" else None,
    }
