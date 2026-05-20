"""client cnpj and access credentials vault

Revision ID: 202605200005
Revises: 202605200004
Create Date: 2026-05-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202605200005"
down_revision: Union[str, None] = "202605200004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("cnpj", sa.String(length=18), nullable=True))
    op.create_unique_constraint("uq_clients_cnpj", "clients", ["cnpj"])

    op.create_table(
        "client_access_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("access_url", sa.String(length=500), nullable=True),
        sa.Column("username", sa.String(length=180), nullable=True),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("notes_encrypted", sa.Text(), nullable=True),
        sa.Column("reveal_token_hash", sa.String(length=255), nullable=False),
        sa.Column("created_by_agent_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_client_access_credentials_client_id",
        "client_access_credentials",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_client_access_credentials_client_id", table_name="client_access_credentials")
    op.drop_table("client_access_credentials")
    op.drop_constraint("uq_clients_cnpj", "clients", type_="unique")
    op.drop_column("clients", "cnpj")
