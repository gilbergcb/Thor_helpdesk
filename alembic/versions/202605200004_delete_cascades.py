"""delete cascades for admin removals

Revision ID: 202605200004
Revises: 202605200003
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "202605200004"
down_revision: Union[str, None] = "202605200003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CHANGES = [
    # (table, constraint_name, column, referred_table, referred_column, ondelete)
    ("whatsapp_groups", "whatsapp_groups_client_id_fkey", "client_id", "clients", "id", "CASCADE"),
    ("whatsapp_users", "whatsapp_users_group_id_fkey", "group_id", "whatsapp_groups", "id", "CASCADE"),
    ("tickets", "tickets_client_id_fkey", "client_id", "clients", "id", "CASCADE"),
    ("tickets", "tickets_whatsapp_group_id_fkey", "whatsapp_group_id", "whatsapp_groups", "id", "CASCADE"),
    ("tickets", "tickets_requester_id_fkey", "requester_id", "whatsapp_users", "id", "SET NULL"),
    ("tickets", "tickets_assigned_agent_id_fkey", "assigned_agent_id", "agents", "id", "SET NULL"),
    ("tickets", "tickets_category_id_fkey", "category_id", "categories", "id", "SET NULL"),
    ("ticket_messages", "ticket_messages_ticket_id_fkey", "ticket_id", "tickets", "id", "CASCADE"),
    ("ticket_messages", "ticket_messages_sender_id_fkey", "sender_id", "whatsapp_users", "id", "SET NULL"),
    ("ticket_messages", "ticket_messages_agent_id_fkey", "agent_id", "agents", "id", "SET NULL"),
    ("ticket_history", "ticket_history_ticket_id_fkey", "ticket_id", "tickets", "id", "CASCADE"),
    ("ticket_history", "ticket_history_agent_id_fkey", "agent_id", "agents", "id", "SET NULL"),
]


def upgrade() -> None:
    for table, name, col, ref_table, ref_col, ondelete in CHANGES:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}')
        op.create_foreign_key(name, table, ref_table, [col], [ref_col], ondelete=ondelete)


def downgrade() -> None:
    for table, name, col, ref_table, ref_col, _ in CHANGES:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}')
        op.create_foreign_key(name, table, ref_table, [col], [ref_col])
