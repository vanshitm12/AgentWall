from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Agent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
