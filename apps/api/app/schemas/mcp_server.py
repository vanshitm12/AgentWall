from datetime import datetime

from pydantic import BaseModel, Field


class MCPServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    endpoint: str
    transport_type: str = Field(..., pattern="^(sse|streamable_http)$")
    trust_level: str = Field(default="TRUSTED", pattern="^(TRUSTED|UNTRUSTED|QUARANTINED)$")
    metadata: dict = Field(default_factory=dict)


class MCPServerResponse(BaseModel):
    id: str
    name: str
    endpoint: str
    transport_type: str
    status: str
    trust_level: str
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MCPServerUpdate(BaseModel):
    name: str | None = None
    endpoint: str | None = None
    transport_type: str | None = None
    status: str | None = None
    trust_level: str | None = None
    metadata: dict | None = None
