from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.approvals import router as approvals_router
from app.api.audit import router as audit_router
from app.api.policies import router as policies_router
from app.api.servers import router as servers_router
from app.api.tools import router as tools_router
from app.config import settings
from app.database import engine
from app.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    yield
    await engine.dispose()
    await redis_client.close()


app = FastAPI(
    title="AgentWall",
    description="Runtime Security Firewall for AI Agents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents_router, prefix="/api/v1")
app.include_router(servers_router, prefix="/api/v1")
app.include_router(tools_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agentwall-api"}


@app.get("/api/v1/overview")
async def overview():
    return {
        "service": "AgentWall",
        "version": "0.1.0",
        "environment": settings.environment,
    }
