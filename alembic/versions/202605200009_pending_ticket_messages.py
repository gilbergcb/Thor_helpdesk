"""pending ticket messages

Revision ID: 202605200009
Revises: 202605200008
Create Date: 2026-05-20 14:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202605200009"
down_revision: str | None = "202605200008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_ticket_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("whatsapp_group_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=True),
        sa.Column("linked_ticket_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_type", sa.String(length=32), nullable=True),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("media_mime_type", sa.String(length=128), nullable=True),
        sa.Column("media_storage_key", sa.String(length=255), nullable=True),
        sa.Column("external_message_id", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["linked_ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sender_id"], ["whatsapp_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["whatsapp_group_id"], ["whatsapp_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pending_ticket_messages_group_status_created",
        "pending_ticket_messages",
        ["whatsapp_group_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pending_ticket_messages_external_message_id"),
        "pending_ticket_messages",
        ["external_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pending_ticket_messages_status"),
        "pending_ticket_messages",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pending_ticket_messages_status"), table_name="pending_ticket_messages")
    op.drop_index(op.f("ix_pending_ticket_messages_external_message_id"), table_name="pending_ticket_messages")
    op.drop_index("ix_pending_ticket_messages_group_status_created", table_name="pending_ticket_messages")
    op.drop_table("pending_ticket_messages")
