"""agent must change password

Revision ID: 202605200008
Revises: 202605200007
Create Date: 2026-05-20 09:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202605200008"
down_revision: str | None = "202605200007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("agents", "must_change_password", server_default=None)


def downgrade() -> None:
    op.drop_column("agents", "must_change_password")
