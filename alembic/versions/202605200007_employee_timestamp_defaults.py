"""employee timestamp defaults

Revision ID: 202605200007
Revises: 202605200006
Create Date: 2026-05-20 08:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202605200007"
down_revision: str | None = "202605200006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("employee_roles", "created_at", server_default=sa.text("now()"))
    op.alter_column("employee_roles", "updated_at", server_default=sa.text("now()"))
    op.alter_column("client_employees", "created_at", server_default=sa.text("now()"))
    op.alter_column("client_employees", "updated_at", server_default=sa.text("now()"))


def downgrade() -> None:
    op.alter_column("client_employees", "updated_at", server_default=None)
    op.alter_column("client_employees", "created_at", server_default=None)
    op.alter_column("employee_roles", "updated_at", server_default=None)
    op.alter_column("employee_roles", "created_at", server_default=None)
