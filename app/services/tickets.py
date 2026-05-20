from datetime import UTC, datetime

from sqlalchemy.orm import Session

from fastapi import HTTPException, status as http_status

from app.models.enums import AgentRole, HistoryEventType, MessageDirection, TicketStatus
from app.models.support import Agent
from app.models.ticket import Ticket, TicketHistory, TicketMessage
from app.repositories.agents import AgentRepository
from app.repositories.tickets import TicketRepository
from app.services.zapi import ZApiClient


class TicketService:
    def __init__(self, db: Session):
        self.db = db
        self.tickets = TicketRepository(db)
        self.agents = AgentRepository(db)

    def kanban(self, viewer: Agent | None = None) -> dict[TicketStatus, list[Ticket]]:
        columns = {status: [] for status in TicketStatus}
        scope = viewer.id if viewer and viewer.role == AgentRole.atendente else None
        for ticket in self.tickets.list_kanban(agent_id_scope=scope):
            columns[ticket.status].append(ticket)
        return columns

    def get_detail(self, ticket_id: int) -> Ticket | None:
        return self.tickets.get_detail(ticket_id)

    def assign(self, ticket_id: int, current_agent: Agent, agent_id: int | None = None) -> Ticket | None:
        ticket = self.db.get(Ticket, ticket_id)
        if ticket is None:
            return None
        assigning_other = agent_id is not None and agent_id != current_agent.id
        if assigning_other and current_agent.role == AgentRole.atendente:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Atendente só pode assumir o próprio ticket",
            )
        assigned_agent = current_agent if agent_id is None else self.agents.get(agent_id)
        if assigned_agent is None:
            return None
        ticket.assigned_agent = assigned_agent
        if ticket.status == TicketStatus.novo:
            ticket.status = TicketStatus.em_atendimento
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=current_agent,
                event_type=HistoryEventType.ticket_assigned,
                description=f"Ticket assumido por {assigned_agent.name}",
            )
        )
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def change_status(self, ticket_id: int, status: TicketStatus, agent: Agent) -> Ticket | None:
        ticket = self.db.get(Ticket, ticket_id)
        if ticket is None:
            return None
        if status == TicketStatus.fechado and agent.role == AgentRole.atendente:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Apenas supervisor ou administrador pode fechar ticket",
            )
        old_status = ticket.status
        ticket.status = status
        if status in (TicketStatus.resolvido, TicketStatus.fechado):
            ticket.closed_at = datetime.now(UTC)
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=agent,
                event_type=HistoryEventType.status_changed,
                description=f"Status alterado de {old_status.value} para {status.value}",
            )
        )
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    async def reply(self, ticket_id: int, message: str, agent: Agent) -> TicketMessage | None:
        ticket = self.tickets.get_detail(ticket_id)
        if ticket is None:
            return None
        result = await ZApiClient().send_group_message(ticket.whatsapp_group.group_id, message)
        external_id = result.get("messageId") or result.get("id")
        saved = TicketMessage(
            ticket=ticket,
            direction=MessageDirection.outbound,
            content=message,
            external_message_id=external_id,
            agent=agent,
        )
        self.db.add(saved)
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=agent,
                event_type=HistoryEventType.message_sent,
                description="Resposta enviada ao grupo via Z-API",
            )
        )
        self.db.commit()
        self.db.refresh(saved)
        return saved
