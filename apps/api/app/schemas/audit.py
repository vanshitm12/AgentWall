from datetime import datetime

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: str
    timestamp: datetime
    agent_id: str
    session_id: str
    server_id: str | None
    tool_name: str
    decision: str
    policy_id: str | None
    risk_score: int | None
    risk_level: str | None
    arguments: dict | None
    response: dict | None
    approval_id: str | None
    latency_ms: int | None
    error: str | None
    metadata: dict

    model_config = {"from_attributes": True}


class AuditEventListResponse(BaseModel):
    events: list[AuditEventResponse]
    total: int
    page: int
    page_size: int
