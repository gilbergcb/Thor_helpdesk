from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import TicketStatus
from app.models.ticket import Ticket
from app.models.whatsapp import WhatsAppUser
from app.models.client import ClientEmployee

OPEN_STATUSES = (
    TicketStatus.novo,
    TicketStatus.triagem,
    TicketStatus.em_atendimento,
    TicketStatus.aguardando_cliente,
)


class TicketRepository:
    def __init__(self, db: Session):
        self.db = db

    def next_protocol(self) -> str:
        today = datetime.now(UTC).strftime("%Y%m%d")
        total_today = self.db.scalar(
            select(func.count(Ticket.id)).where(Ticket.protocol.like(f"{today}-%"))
        )
        return f"{today}-{total_today + 1:05d}"

    def latest_open_for_group(self, group_id: int) -> Ticket | None:
        return self.db.scalar(
            select(Ticket)
            .where(Ticket.whatsapp_group_id == group_id, Ticket.status.in_(OPEN_STATUSES))
            .order_by(desc(Ticket.created_at))
            .limit(1)
        )

    def list_kanban(self, agent_id_scope: int | None = None) -> list[Ticket]:
        stmt = (
            select(Ticket)
            .options(
                joinedload(Ticket.client),
                joinedload(Ticket.whatsapp_group),
                joinedload(Ticket.requester)
                .joinedload(WhatsAppUser.employee)
                .joinedload(ClientEmployee.role),
                joinedload(Ticket.assigned_agent),
            )
            .order_by(desc(Ticket.created_at))
        )
        if agent_id_scope is not None:
            stmt = stmt.where(
                (Ticket.assigned_agent_id.is_(None)) | (Ticket.assigned_agent_id == agent_id_scope)
            )
        return list(self.db.scalars(stmt))

    def get_detail(self, ticket_id: int) -> Ticket | None:
        return self.db.scalar(
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                joinedload(Ticket.client),
                joinedload(Ticket.whatsapp_group),
                joinedload(Ticket.requester)
                .joinedload(WhatsAppUser.employee)
                .joinedload(ClientEmployee.role),
                joinedload(Ticket.assigned_agent),
                selectinload(Ticket.messages),
            )
        )
