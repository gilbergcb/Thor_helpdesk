"""agent role column

Revision ID: 202605200003
Revises: 202605200002
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202605200003"
down_revision: Union[str, None] = "202605200002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    role_enum = sa.Enum("atendente", "supervisor", "administrador", name="agent_role")
    role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "agents",
        sa.Column("role", role_enum, nullable=False, server_default="atendente"),
    )
    op.execute(
        "UPDATE agents SET role='administrador' WHERE email='admin@helpdesk.com.br'"
    )
    op.alter_column("agents", "role", server_default=None)


def downgrade() -> None:
    op.drop_column("agents", "role")
    sa.Enum(name="agent_role").drop(op.get_bind(), checkfirst=True)
