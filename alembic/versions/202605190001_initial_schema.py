"""initial schema

Revision ID: 202605190001
Revises:
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202605190001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ticket_status = sa.Enum(
        "novo",
        "triagem",
        "em_atendimento",
        "aguardando_cliente",
        "resolvido",
        "fechado",
        name="ticket_status",
        create_type=False,
    )
    ticket_priority = sa.Enum(
        "baixa", "media", "alta", "critica", name="ticket_priority", create_type=False
    )
    message_direction = sa.Enum("inbound", "outbound", name="message_direction", create_type=False)
    history_event_type = sa.Enum(
        "ticket_created",
        "ticket_assigned",
        "message_received",
        "message_sent",
        "status_changed",
        name="history_event_type",
        create_type=False,
    )
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agents_email"), "agents", ["email"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("document", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document"),
    )
    op.create_table(
        "whatsapp_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_whatsapp_groups_group_id"), "whatsapp_groups", ["group_id"], unique=True)
    op.create_table(
        "whatsapp_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["whatsapp_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "phone", name="uq_whatsapp_user_group_phone"),
    )
    op.create_index(op.f("ix_whatsapp_users_phone"), "whatsapp_users", ["phone"], unique=False)
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("whatsapp_group_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=True),
        sa.Column("assigned_agent_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["whatsapp_users.id"]),
        sa.ForeignKeyConstraint(["whatsapp_group_id"], ["whatsapp_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tickets_protocol"), "tickets", ["protocol"], unique=True)
    op.create_index(op.f("ix_tickets_status"), "tickets", ["status"], unique=False)
    op.create_index(
        "ix_tickets_group_status_created",
        "tickets",
        ["whatsapp_group_id", "status", "created_at"],
        unique=False,
    )
    op.create_table(
        "ticket_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("event_type", history_event_type, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("external_message_id", sa.String(length=128), nullable=True),
        sa.Column("sender_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["whatsapp_users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ticket_messages_external_message_id"),
        "ticket_messages",
        ["external_message_id"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO clients (id, name, document, is_active)
            VALUES (1, 'Cliente Demonstração WinThor', '00000000000191', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO whatsapp_groups (id, client_id, group_id, name, is_active)
            VALUES (1, 1, '5585999999999-group', 'Suporte WinThor - Cliente Demonstração', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO categories (id, name, description)
            VALUES
              (1, 'Fiscal', 'Rotinas fiscais e faturamento'),
              (2, 'Financeiro', 'Contas a pagar, receber e conciliação'),
              (3, 'Estoque', 'Entradas, saídas e inventário')
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO agents (id, name, email, password_hash, is_active)
            VALUES (
              1,
              'Administrador',
              'admin@helpdesk.com.br',
              '$2b$12$5/RgHChRKWIYKiL/ZGkHi.tfPlt9CUub5B15xUxAXXPX19IA1t2z.',
              true
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ticket_messages_external_message_id"), table_name="ticket_messages")
    op.drop_table("ticket_messages")
    op.drop_table("ticket_history")
    op.drop_index("ix_tickets_group_status_created", table_name="tickets")
    op.drop_index(op.f("ix_tickets_status"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_protocol"), table_name="tickets")
    op.drop_table("tickets")
    op.drop_index(op.f("ix_whatsapp_users_phone"), table_name="whatsapp_users")
    op.drop_table("whatsapp_users")
    op.drop_index(op.f("ix_whatsapp_groups_group_id"), table_name="whatsapp_groups")
    op.drop_table("whatsapp_groups")
    op.drop_table("clients")
    op.drop_table("categories")
    op.drop_index(op.f("ix_agents_email"), table_name="agents")
    op.drop_table("agents")
    sa.Enum(name="history_event_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="message_direction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ticket_priority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ticket_status").drop(op.get_bind(), checkfirst=True)
