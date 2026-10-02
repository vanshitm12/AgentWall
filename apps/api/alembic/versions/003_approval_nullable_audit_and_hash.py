"""Make approval audit_event_id nullable and add arguments_hash

Revision ID: 003
Revises: 002
Create Date: 2026-10-03

audit_event_id is nullable because audit logging (Phase 5) isn't built yet.
arguments_hash enables matching agent retries to existing approvals.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("approvals", "audit_event_id", nullable=True)
    op.add_column(
        "approvals",
        sa.Column("arguments_hash", sa.String(64), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("approvals", "arguments_hash")
    op.alter_column("approvals", "audit_event_id", nullable=False)
