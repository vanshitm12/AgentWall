from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class MCPServer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "mcp_servers"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    transport_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    trust_level: Mapped[str] = mapped_column(String(20), nullable=False, default="TRUSTED")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
