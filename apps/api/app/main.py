import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.approvals import router as approvals_router
from app.api.audit import router as audit_router
from app.api.dlp import router as dlp_router
from app.api.killswitch import router as killswitch_router
from app.api.risk import router as risk_router
from app.api.discovery import router as discovery_router
from app.api.policies import router as policies_router
from app.api.servers import router as servers_router
from app.api.tools import router as tools_router
from app.config import settings
from app.database import engine
from app.mcp.downstream import downstream_manager
from app.mcp.proxy import router as mcp_router
from app.redis import redis_client

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    logger.info("AgentWall starting up")
    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")
    yield
    logger.info("AgentWall shutting down")
    await downstream_manager.disconnect_all()
    await engine.dispose()
    await redis_client.close()


app = FastAPI(
    title="AgentWall",
    description="Runtime Security Firewall for AI Agents",
    version="0.1.0",
    lifespan=lifespan,
)

import os
cors_origins = ["http://localhost:3000"]
if os.getenv("DASHBOARD_URL"):
    cors_origins.append(os.getenv("DASHBOARD_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP proxy endpoint (agent-facing)
app.include_router(mcp_router)

# REST API (dashboard / admin)
app.include_router(agents_router, prefix="/api/v1")
app.include_router(servers_router, prefix="/api/v1")
app.include_router(tools_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(risk_router, prefix="/api/v1")
app.include_router(dlp_router, prefix="/api/v1")
app.include_router(killswitch_router, prefix="/api/v1")
app.include_router(discovery_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "agentwall-api",
        "downstream_servers": downstream_manager.connected_count,
        "available_tools": downstream_manager.total_tool_count,
    }


@app.get("/api/v1/overview")
async def overview():
    return {
        "service": "AgentWall",
        "version": "0.1.0",
        "environment": settings.environment,
        "downstream_servers": downstream_manager.connected_count,
        "available_tools": downstream_manager.total_tool_count,
    }
