"""agent totp

Revision ID: 202605220015
Revises: 202605220014
Create Date: 2026-05-22 15:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202605220015"
down_revision: str | None = "202605220014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("totp_secret_encrypted", sa.String(length=255), nullable=True))
    op.add_column(
        "agents",
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("agents", "totp_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("agents", "totp_enabled")
    op.drop_column("agents", "totp_secret_encrypted")
