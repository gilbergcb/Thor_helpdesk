"""ticket message attachments (portal público uploads)

Revision ID: 202605210013
Revises: 202605210012
Create Date: 2026-05-21 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202605210013"
down_revision: str | None = "202605210012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_message_attachments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_message_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["ticket_message_id"], ["ticket_messages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_message_attachments_message",
        "ticket_message_attachments",
        ["ticket_message_id"],
    )
    op.create_index(
        "ix_ticket_message_attachments_created_at",
        "ticket_message_attachments",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticket_message_attachments_created_at",
        table_name="ticket_message_attachments",
    )
    op.drop_index(
        "ix_ticket_message_attachments_message",
        table_name="ticket_message_attachments",
    )
    op.drop_table("ticket_message_attachments")
