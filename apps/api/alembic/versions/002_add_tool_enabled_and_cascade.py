"""Add tool enabled column and cascade delete

Revision ID: 002
Revises: 001
Create Date: 2026-09-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tools", sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"))

    op.drop_constraint("tools_server_id_fkey", "tools", type_="foreignkey")
    op.create_foreign_key(
        "tools_server_id_fkey",
        "tools",
        "mcp_servers",
        ["server_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("tools_server_id_fkey", "tools", type_="foreignkey")
    op.create_foreign_key(
        "tools_server_id_fkey",
        "tools",
        "mcp_servers",
        ["server_id"],
        ["id"],
    )
    op.drop_column("tools", "enabled")
