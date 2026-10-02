"""Set audit_events FKs to SET NULL on delete

Revision ID: 004
Revises: 003
Create Date: 2026-10-03

Audit events are historical records. When a policy, server, or agent
is deleted, the audit events should survive with the FK set to NULL.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("audit_events_policy_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_policy_id_fkey", "audit_events", "policies",
        ["policy_id"], ["id"], ondelete="SET NULL",
    )

    op.drop_constraint("audit_events_server_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_server_id_fkey", "audit_events", "mcp_servers",
        ["server_id"], ["id"], ondelete="SET NULL",
    )

    op.drop_constraint("audit_events_agent_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_agent_id_fkey", "audit_events", "agents",
        ["agent_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("audit_events_agent_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_agent_id_fkey", "audit_events", "agents",
        ["agent_id"], ["id"],
    )

    op.drop_constraint("audit_events_server_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_server_id_fkey", "audit_events", "mcp_servers",
        ["server_id"], ["id"],
    )

    op.drop_constraint("audit_events_policy_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_policy_id_fkey", "audit_events", "policies",
        ["policy_id"], ["id"],
    )
