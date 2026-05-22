from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.client import ClientEmployee
from app.models.enums import TicketStatus
from app.models.ticket import PendingTicketMessage, Ticket
from app.models.whatsapp import WhatsAppUser

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
        latest_protocol = self.db.scalar(
            select(Ticket.protocol)
            .where(Ticket.protocol.like(f"{today}-%"))
            .order_by(desc(Ticket.protocol))
            .limit(1)
        )
        if not latest_protocol:
            return f"{today}-00001"
        try:
            latest_number = int(latest_protocol.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            latest_number = 0
        return f"{today}-{latest_number + 1:05d}"

    def latest_open_for_group(self, group_id: int) -> Ticket | None:
        return self.db.scalar(
            select(Ticket)
            .where(Ticket.whatsapp_group_id == group_id, Ticket.status.in_(OPEN_STATUSES))
            .order_by(desc(Ticket.created_at))
            .limit(1)
        )

    def get_by_protocol(self, protocol: str) -> Ticket | None:
        return self.db.scalar(select(Ticket).where(Ticket.protocol == protocol))

    def pending_for_group(
        self,
        group_id: int,
        created_at_from: datetime | None = None,
    ) -> list[PendingTicketMessage]:
        filters = [
            PendingTicketMessage.whatsapp_group_id == group_id,
            PendingTicketMessage.status == "pending",
        ]
        if created_at_from is not None:
            filters.append(PendingTicketMessage.created_at >= created_at_from)
        return list(
            self.db.scalars(
                select(PendingTicketMessage)
                .where(*filters)
                .options(joinedload(PendingTicketMessage.sender))
                .order_by(PendingTicketMessage.created_at)
            )
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
