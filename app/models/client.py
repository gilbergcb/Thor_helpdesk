from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.mixins import TimestampMixin
from app.core.database import Base


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    document: Mapped[str | None] = mapped_column(String(32), unique=True)
    cnpj: Mapped[str | None] = mapped_column(String(18), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    whatsapp_groups = relationship(
        "WhatsAppGroup", back_populates="client", cascade="all, delete", passive_deletes=True
    )
    tickets = relationship(
        "Ticket", back_populates="client", cascade="all, delete", passive_deletes=True
    )
    access_credentials = relationship(
        "ClientAccessCredential",
        back_populates="client",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    employees = relationship(
        "ClientEmployee",
        secondary="whatsapp_groups",
        primaryjoin="Client.id == WhatsAppGroup.client_id",
        secondaryjoin="WhatsAppGroup.id == ClientEmployee.whatsapp_group_id",
        viewonly=True,
    )


class ClientAccessCredential(TimestampMixin, Base):
    __tablename__ = "client_access_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    access_url: Mapped[str | None] = mapped_column(String(500))
    username: Mapped[str | None] = mapped_column(String(180))
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    notes_encrypted: Mapped[str | None] = mapped_column(Text)
    reveal_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client = relationship("Client", back_populates="access_credentials")
    created_by_agent = relationship("Agent")


class EmployeeRole(TimestampMixin, Base):
    __tablename__ = "employee_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employees = relationship("ClientEmployee", back_populates="role")


class ClientEmployee(TimestampMixin, Base):
    __tablename__ = "client_employees"
    __table_args__ = (
        UniqueConstraint("whatsapp_group_id", "phone", name="uq_client_employee_group_phone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    whatsapp_group_id: Mapped[int] = mapped_column(
        ForeignKey("whatsapp_groups.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[int | None] = mapped_column(ForeignKey("employee_roles.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(180))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    whatsapp_group = relationship("WhatsAppGroup", back_populates="employees")
    role = relationship("EmployeeRole", back_populates="employees")
    whatsapp_users = relationship("WhatsAppUser", back_populates="employee")

    @property
    def client(self) -> Client:
        return self.whatsapp_group.client
