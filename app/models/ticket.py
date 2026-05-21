from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import HistoryEventType, MessageDirection, TicketPriority, TicketStatus
from app.models.mixins import TimestampMixin


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    protocol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status"),
        default=TicketStatus.novo,
        index=True,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority"),
        default=TicketPriority.media,
        nullable=False,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    whatsapp_group_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_groups.id"), nullable=False)
    requester_id: Mapped[int | None] = mapped_column(ForeignKey("whatsapp_users.id"))
    assigned_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))

    client = relationship("Client", back_populates="tickets")
    whatsapp_group = relationship("WhatsAppGroup", back_populates="tickets")
    requester = relationship("WhatsAppUser")
    assigned_agent = relationship("Agent", back_populates="tickets")
    category = relationship("Category", back_populates="tickets")
    messages = relationship(
        "TicketMessage", back_populates="ticket", cascade="all, delete-orphan", passive_deletes=True
    )
    history = relationship(
        "TicketHistory", back_populates="ticket", cascade="all, delete-orphan", passive_deletes=True
    )
    public_links = relationship(
        "TicketPublicLink",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


Index("ix_tickets_group_status_created", Ticket.whatsapp_group_id, Ticket.status, Ticket.created_at)


class TicketPublicLink(TimestampMixin, Base):
    __tablename__ = "ticket_public_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_access_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ticket = relationship("Ticket", back_populates="public_links")


class TicketMessage(TimestampMixin, Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="message_direction"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_type: Mapped[str | None] = mapped_column(String(32))
    media_url: Mapped[str | None] = mapped_column(Text)
    media_mime_type: Mapped[str | None] = mapped_column(String(128))
    media_storage_key: Mapped[str | None] = mapped_column(String(255))
    external_message_id: Mapped[str | None] = mapped_column(String(128), index=True)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("whatsapp_users.id"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))

    ticket = relationship("Ticket", back_populates="messages")
    sender = relationship("WhatsAppUser", back_populates="messages")
    agent = relationship("Agent", back_populates="sent_messages")


class PendingTicketMessage(TimestampMixin, Base):
    __tablename__ = "pending_ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    whatsapp_group_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_groups.id"), nullable=False)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("whatsapp_users.id"))
    linked_ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_type: Mapped[str | None] = mapped_column(String(32))
    media_url: Mapped[str | None] = mapped_column(Text)
    media_mime_type: Mapped[str | None] = mapped_column(String(128))
    media_storage_key: Mapped[str | None] = mapped_column(String(255))
    external_message_id: Mapped[str | None] = mapped_column(String(128), index=True)
    reason: Mapped[str | None] = mapped_column(String(180))

    whatsapp_group = relationship("WhatsAppGroup")
    sender = relationship("WhatsAppUser")
    linked_ticket = relationship("Ticket")


Index(
    "ix_pending_ticket_messages_group_status_created",
    PendingTicketMessage.whatsapp_group_id,
    PendingTicketMessage.status,
    PendingTicketMessage.created_at,
)


class TicketHistory(TimestampMixin, Base):
    __tablename__ = "ticket_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    event_type: Mapped[HistoryEventType] = mapped_column(
        Enum(HistoryEventType, name="history_event_type"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))

    ticket = relationship("Ticket", back_populates="history")
    agent = relationship("Agent")
