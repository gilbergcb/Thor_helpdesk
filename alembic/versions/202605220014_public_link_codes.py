"""public link short codes

Revision ID: 202605220014
Revises: 202605210013
Create Date: 2026-05-22 14:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605220014"
down_revision: str | None = "202605210013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ticket_public_links",
        sa.Column("code_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_ticket_public_links_code_hash"),
        "ticket_public_links",
        ["code_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ticket_public_links_code_hash"),
        table_name="ticket_public_links",
    )
    op.drop_column("ticket_public_links", "code_hash")
