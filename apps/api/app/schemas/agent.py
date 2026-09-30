from datetime import datetime

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    metadata: dict = Field(default_factory=dict)


class AgentCreateResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    api_key: str
    api_key_prefix: str
    created_at: datetime


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    api_key_prefix: str
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    metadata: dict | None = None


class AgentStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|SUSPENDED|KILLED)$")
