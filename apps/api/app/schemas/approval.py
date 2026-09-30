from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalResponse(BaseModel):
    id: str
    audit_event_id: str
    agent_id: str
    tool_name: str
    arguments: dict | None
    status: str
    risk_score: int | None
    risk_level: str | None
    reason: str | None
    reviewer: str | None
    decided_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reviewer: str = Field(..., min_length=1)
    reason: str | None = None
