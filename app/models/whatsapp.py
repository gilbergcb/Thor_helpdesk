from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class WhatsAppGroup(TimestampMixin, Base):
    __tablename__ = "whatsapp_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    group_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client = relationship("Client", back_populates="whatsapp_groups")
    users = relationship(
        "WhatsAppUser", back_populates="group", cascade="all, delete", passive_deletes=True
    )
    employees = relationship(
        "ClientEmployee", back_populates="whatsapp_group", cascade="all, delete", passive_deletes=True
    )
    tickets = relationship(
        "Ticket", back_populates="whatsapp_group", cascade="all, delete", passive_deletes=True
    )


class WhatsAppUser(TimestampMixin, Base):
    __tablename__ = "whatsapp_users"
    __table_args__ = (UniqueConstraint("group_id", "phone", name="uq_whatsapp_user_group_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("whatsapp_groups.id"), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(160))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("client_employees.id", ondelete="SET NULL"))

    group = relationship("WhatsAppGroup", back_populates="users")
    employee = relationship("ClientEmployee", back_populates="whatsapp_users")
    messages = relationship("TicketMessage", back_populates="sender")

    @property
    def employee_role(self):
        return self.employee.role if self.employee else None
