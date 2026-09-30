"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-09-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("api_key_hash", sa.String(64), nullable=False),
        sa.Column("api_key_prefix", sa.String(12), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "mcp_servers",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("transport_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("trust_level", sa.String(20), nullable=False, server_default="TRUSTED"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "tools",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "server_id",
            UUID(as_uuid=False),
            sa.ForeignKey("mcp_servers.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("input_schema", JSONB, nullable=True),
        sa.Column(
            "risk_classification", sa.String(20), nullable=False, server_default="MEDIUM"
        ),
        sa.Column("audit_log_level", sa.String(20), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("server_id", "name", name="uq_tool_server_name"),
    )

    op.create_table(
        "policies",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("cedar_policy", sa.Text, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=False),
            sa.ForeignKey("agents.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column(
            "server_id",
            UUID(as_uuid=False),
            sa.ForeignKey("mcp_servers.id"),
            nullable=True,
        ),
        sa.Column("tool_name", sa.String(255), nullable=False, index=True),
        sa.Column("decision", sa.String(20), nullable=False, index=True),
        sa.Column(
            "policy_id",
            UUID(as_uuid=False),
            sa.ForeignKey("policies.id"),
            nullable=True,
        ),
        sa.Column("risk_score", sa.Integer, nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("arguments", JSONB, nullable=True),
        sa.Column("response", JSONB, nullable=True),
        sa.Column("approval_id", UUID(as_uuid=False), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    op.create_table(
        "approvals",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "audit_event_id",
            UUID(as_uuid=False),
            sa.ForeignKey("audit_events.id"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=False),
            sa.ForeignKey("agents.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("arguments", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING", index=True),
        sa.Column("risk_score", sa.Integer, nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("reviewer", sa.String(255), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("approvals")
    op.drop_table("audit_events")
    op.drop_table("policies")
    op.drop_table("tools")
    op.drop_table("mcp_servers")
    op.drop_table("agents")
