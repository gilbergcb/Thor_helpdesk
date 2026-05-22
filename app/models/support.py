from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import AgentRole
from app.models.mixins import TimestampMixin


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(String(255))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, name="agent_role"),
        default=AgentRole.atendente,
        nullable=False,
    )

    tickets = relationship("Ticket", back_populates="assigned_agent")
    sent_messages = relationship("TicketMessage", back_populates="agent")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    tickets = relationship("Ticket", back_populates="category")
