"""Kill switch REST API.

Provides instant agent termination via Redis (faster than DB status changes).
Two levels: per-agent and global (emergency).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.killswitch.engine import (
    activate_agent,
    activate_global,
    deactivate_agent,
    deactivate_global,
    get_agent_status,
    get_global_status,
)
from app.mcp.session import session_manager

router = APIRouter(prefix="/killswitch", tags=["killswitch"])


class KillSwitchRequest(BaseModel):
    reason: str = ""


class AgentKillSwitchResponse(BaseModel):
    agent_id: str
    active: bool
    reason: str | None = None
    sessions_destroyed: int = 0


class GlobalKillSwitchResponse(BaseModel):
    active: bool
    reason: str | None = None


@router.post("/agent/{agent_id}", response_model=AgentKillSwitchResponse)
async def activate_agent_killswitch(agent_id: str, body: KillSwitchRequest | None = None):
    """Activate kill switch for a specific agent. Instant effect."""
    reason = body.reason if body else ""
    await activate_agent(agent_id, reason)
    destroyed = await session_manager.destroy_all_for_agent(agent_id)
    return AgentKillSwitchResponse(
        agent_id=agent_id,
        active=True,
        reason=reason or None,
        sessions_destroyed=destroyed,
    )


@router.delete("/agent/{agent_id}", response_model=AgentKillSwitchResponse)
async def deactivate_agent_killswitch(agent_id: str):
    """Deactivate kill switch for a specific agent."""
    await deactivate_agent(agent_id)
    return AgentKillSwitchResponse(agent_id=agent_id, active=False)


@router.get("/agent/{agent_id}", response_model=AgentKillSwitchResponse)
async def get_agent_killswitch(agent_id: str):
    """Check kill switch status for a specific agent."""
    status = await get_agent_status(agent_id)
    return AgentKillSwitchResponse(**status)


@router.post("/global", response_model=GlobalKillSwitchResponse)
async def activate_global_killswitch(body: KillSwitchRequest | None = None):
    """Activate global kill switch. ALL agents are immediately blocked."""
    reason = body.reason if body else ""
    await activate_global(reason)
    return GlobalKillSwitchResponse(active=True, reason=reason or None)


@router.delete("/global", response_model=GlobalKillSwitchResponse)
async def deactivate_global_killswitch():
    """Deactivate global kill switch."""
    await deactivate_global()
    return GlobalKillSwitchResponse(active=False)


@router.get("/global", response_model=GlobalKillSwitchResponse)
async def get_global_killswitch():
    """Check global kill switch status."""
    status = await get_global_status()
    return GlobalKillSwitchResponse(**status)
