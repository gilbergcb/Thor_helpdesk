"""agent phone

Revision ID: 202605210010
Revises: 202605200009
Create Date: 2026-05-21 00:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202605210010"
down_revision: str | None = "202605200009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("phone", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_agents_phone"), "agents", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_agents_phone"), table_name="agents")
    op.drop_column("agents", "phone")
