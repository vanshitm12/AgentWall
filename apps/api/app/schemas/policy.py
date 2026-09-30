from datetime import datetime

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    cedar_policy: str = Field(..., min_length=1)
    priority: int = Field(default=0)
    enabled: bool = Field(default=True)
    metadata: dict = Field(default_factory=dict)


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: str | None
    cedar_policy: str
    priority: int
    enabled: bool
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cedar_policy: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    metadata: dict | None = None
