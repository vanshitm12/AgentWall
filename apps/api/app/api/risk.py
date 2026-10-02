"""Risk assessment REST API.

Provides endpoints for querying risk scores without making an actual tool call.
Useful for dashboards, dry-run assessments, and understanding risk posture.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.risk.engine import score_tool_call, RiskResult

router = APIRouter(prefix="/risk", tags=["risk"])


class RiskAssessRequest(BaseModel):
    agent_id: str
    tool_name: str
    risk_classification: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    server_trust_level: str = Field(default="TRUSTED", pattern="^(TRUSTED|UNTRUSTED|UNKNOWN)$")
    arguments: dict | None = None
    dry_run: bool = Field(default=True, description="If true, does not update velocity counters")


class RiskAssessResponse(BaseModel):
    score: int
    level: str
    factors: list[str]
    auto_deny: bool


@router.post("/assess", response_model=RiskAssessResponse)
async def assess_risk(req: RiskAssessRequest):
    """Assess the risk score for a hypothetical tool call."""
    result = await score_tool_call(
        agent_id=req.agent_id,
        tool_name=req.tool_name,
        risk_classification=req.risk_classification,
        server_trust_level=req.server_trust_level,
        arguments=req.arguments,
        dry_run=req.dry_run,
    )

    from app.config import settings
    return RiskAssessResponse(
        score=result.score,
        level=result.level,
        factors=result.factors,
        auto_deny=result.score >= settings.risk_auto_deny_threshold,
    )
