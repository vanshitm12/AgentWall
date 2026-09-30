from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AuditEvent(UUIDMixin, Base):
    __tablename__ = "audit_events"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agents.id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    server_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("mcp_servers.id"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    policy_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("policies.id"), nullable=True
    )
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    arguments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approval_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
