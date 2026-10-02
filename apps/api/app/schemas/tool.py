from datetime import datetime

from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    id: str
    server_id: str
    name: str
    description: str | None
    input_schema: dict | None
    risk_classification: str
    audit_log_level: str | None
    enabled: bool
    metadata: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolUpdate(BaseModel):
    risk_classification: str | None = Field(
        default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"
    )
    audit_log_level: str | None = None
    enabled: bool | None = None
    metadata: dict | None = None
