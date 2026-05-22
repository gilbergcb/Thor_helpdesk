import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.models.enums import AgentRole, HistoryEventType, MessageDirection, TicketStatus
from app.models.support import Agent
from app.models.ticket import PendingTicketMessage, Ticket, TicketHistory, TicketMessage
from app.repositories.agents import AgentRepository
from app.repositories.tickets import TicketRepository
from app.services.public_links import PublicTicketLinkService
from app.services.zapi import ZApiClient

logger = logging.getLogger(__name__)


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
        ticket = self.tickets.get_detail(ticket_id)
        if ticket is not None:
            ticket.pending_messages = self.tickets.pending_for_group(
                ticket.whatsapp_group_id,
                created_at_from=ticket.opened_at,
            )
        return ticket

    async def assign(
        self,
        ticket_id: int,
        current_agent: Agent,
        agent_id: int | None = None,
    ) -> Ticket | None:
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
        await self._send_assignment_notice(ticket, assigned_agent)
        return ticket

    async def change_status(
        self,
        ticket_id: int,
        status: TicketStatus,
        agent: Agent,
    ) -> Ticket | None:
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
        # Revoga link publico em qualquer transicao para um estado terminal —
        # resolvido (atendente julga concluido) ou fechado (cliente confirmou).
        if status in (TicketStatus.resolvido, TicketStatus.fechado):
            PublicTicketLinkService(self.db).revoke_for_ticket(ticket)
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
        if old_status != status:
            if status == TicketStatus.aguardando_cliente:
                await self._send_waiting_customer_notice(ticket, agent)
            elif status == TicketStatus.resolvido:
                await self._send_resolution_notice(ticket, agent)
            elif status == TicketStatus.fechado:
                await self._send_closed_notice(ticket, agent)
        return ticket

    async def reply(self, ticket_id: int, message: str, agent: Agent) -> TicketMessage | None:
        ticket = self.tickets.get_detail(ticket_id)
        if ticket is None:
            return None
        outbound_message = self._message_with_agent_signature(message, agent)
        result = await ZApiClient().send_group_message(
            ticket.whatsapp_group.group_id,
            outbound_message,
        )
        external_id = result.get("messageId") or result.get("id")
        saved = TicketMessage(
            ticket=ticket,
            direction=MessageDirection.outbound,
            content=outbound_message,
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

    @staticmethod
    def _message_with_agent_signature(message: str, agent: Agent) -> str:
        identity = agent.name
        if agent.phone:
            identity = f"{identity} ({agent.phone})"
        return f"Atendente THOR: {identity}\n\n{message}"

    async def _send_assignment_notice(self, ticket: Ticket, agent: Agent) -> None:
        identity = agent.name
        if agent.phone:
            identity = f"{identity} ({agent.phone})"
        message = (
            f"O chamado {ticket.protocol} foi assumido por {identity}.\n\n"
            "Vamos acompanhar o atendimento por aqui."
        )
        try:
            result = await ZApiClient().send_group_message(ticket.whatsapp_group.group_id, message)
        except Exception as exc:
            logger.warning("Falha ao avisar assunção do ticket %s: %s", ticket.id, exc)
            return
        external_id = result.get("messageId") or result.get("id")
        self.db.add(
            TicketMessage(
                ticket=ticket,
                direction=MessageDirection.outbound,
                content=message,
                external_message_id=external_id,
                agent=agent,
            )
        )
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=agent,
                event_type=HistoryEventType.message_sent,
                description="Aviso de assunção enviado ao grupo via Z-API",
            )
        )
        self.db.commit()

    async def _send_resolution_notice(self, ticket: Ticket, agent: Agent) -> None:
        identity = agent.name
        if agent.phone:
            identity = f"{identity} ({agent.phone})"
        requester_phone = self._requester_mention_phone(ticket)
        mention_prefix = f"@{requester_phone} " if requester_phone else ""
        message = (
            f"{mention_prefix}O chamado {ticket.protocol} foi marcado como "
            f"resolvido por {identity}.\n\n"
            "Se precisar de algo mais, responda por aqui."
        )
        try:
            result = await ZApiClient().send_group_message(
                ticket.whatsapp_group.group_id,
                message,
                mentioned=[requester_phone] if requester_phone else None,
            )
        except Exception as exc:
            logger.warning("Falha ao avisar resolução do ticket %s: %s", ticket.id, exc)
            return
        external_id = result.get("messageId") or result.get("id")
        self.db.add(
            TicketMessage(
                ticket=ticket,
                direction=MessageDirection.outbound,
                content=message,
                external_message_id=external_id,
                agent=agent,
            )
        )
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=agent,
                event_type=HistoryEventType.message_sent,
                description="Aviso de resolução enviado ao grupo via Z-API",
            )
        )
        self.db.commit()

    async def _send_waiting_customer_notice(self, ticket: Ticket, agent: Agent) -> None:
        requester_phone = self._requester_mention_phone(ticket)
        mention_prefix = f"@{requester_phone} " if requester_phone else ""
        public_link_service = PublicTicketLinkService(self.db)
        public_token = public_link_service.create_for_ticket(ticket)
        public_url = public_link_service.public_url(public_token)
        self.db.commit()

        message = (
            f"{mention_prefix}O chamado {ticket.protocol} está aguardando seu retorno.\n\n"
            "Acesse o link abaixo para visualizar o atendimento e responder pelo portal:\n"
            f"{public_url}\n\n"
            "O link fica ativo até a finalização do chamado."
        )
        try:
            result = await ZApiClient().send_group_message(
                ticket.whatsapp_group.group_id,
                message,
                mentioned=[requester_phone] if requester_phone else None,
            )
        except Exception as exc:
            logger.warning("Falha ao avisar aguardando cliente do ticket %s: %s", ticket.id, exc)
            return
        external_id = result.get("messageId") or result.get("id")
        self.db.add(
            TicketMessage(
                ticket=ticket,
                direction=MessageDirection.outbound,
                content=message,
                external_message_id=external_id,
                agent=agent,
            )
        )
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=agent,
                event_type=HistoryEventType.message_sent,
                description="Aviso de aguardando cliente enviado ao grupo via Z-API",
            )
        )
        self.db.commit()

    async def _send_closed_notice(self, ticket: Ticket, agent: Agent) -> None:
        identity = agent.name
        if agent.phone:
            identity = f"{identity} ({agent.phone})"
        requester_phone = self._requester_mention_phone(ticket)
        mention_prefix = f"@{requester_phone} " if requester_phone else ""
        message = (
            f"{mention_prefix}O chamado {ticket.protocol} foi fechado por {identity}.\n\n"
            "Obrigado pelo retorno. Se precisar de novo atendimento, abra um novo chamado."
        )
        try:
            result = await ZApiClient().send_group_message(
                ticket.whatsapp_group.group_id,
                message,
                mentioned=[requester_phone] if requester_phone else None,
            )
        except Exception as exc:
            logger.warning("Falha ao avisar fechamento do ticket %s: %s", ticket.id, exc)
            return
        external_id = result.get("messageId") or result.get("id")
        self.db.add(
            TicketMessage(
                ticket=ticket,
                direction=MessageDirection.outbound,
                content=message,
                external_message_id=external_id,
                agent=agent,
            )
        )
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=agent,
                event_type=HistoryEventType.message_sent,
                description="Aviso de fechamento enviado ao grupo via Z-API",
            )
        )
        self.db.commit()

    @staticmethod
    def _requester_mention_phone(ticket: Ticket) -> str | None:
        if ticket.requester is None or not ticket.requester.phone:
            return None
        phone = "".join(char for char in ticket.requester.phone if char.isdigit())
        return phone or None

    def link_pending_message(
        self,
        pending_id: int,
        ticket_id: int,
        agent: Agent,
    ) -> TicketMessage | None:
        pending = self.db.get(PendingTicketMessage, pending_id)
        ticket = self.db.get(Ticket, ticket_id)
        if pending is None or ticket is None:
            return None
        if pending.status != "pending":
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Mensagem pendente já foi tratada",
            )
        if pending.whatsapp_group_id != ticket.whatsapp_group_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Mensagem pertence a outro grupo WhatsApp",
            )
        saved = self._copy_pending_to_ticket(pending, ticket)
        pending.status = "linked"
        pending.linked_ticket = ticket
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=agent,
                event_type=HistoryEventType.message_received,
                description=f"Mensagem pendente vinculada por {agent.name}",
            )
        )
        self.db.commit()
        self.db.refresh(saved)
        return saved

    def create_ticket_from_pending(
        self,
        pending_id: int,
        agent: Agent,
        title: str | None = None,
        description: str | None = None,
    ) -> Ticket | None:
        pending = self.db.get(PendingTicketMessage, pending_id)
        if pending is None:
            return None
        if pending.status != "pending":
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Mensagem pendente já foi tratada",
            )
        group = pending.whatsapp_group
        body = (
            description
            or pending.content
            or "Chamado aberto a partir de mensagem pendente"
        ).strip()
        ticket = Ticket(
            protocol=self.tickets.next_protocol(),
            title=(title or body.splitlines()[0] or "Chamado via WhatsApp")[:180],
            description=body,
            opened_at=datetime.now(UTC),
            client=group.client,
            whatsapp_group=group,
            requester=pending.sender,
        )
        self.db.add(ticket)
        self.db.flush()
        self._copy_pending_to_ticket(pending, ticket)
        PublicTicketLinkService(self.db).create_for_ticket(ticket)
        pending.status = "linked"
        pending.linked_ticket = ticket
        self.db.add(
            TicketHistory(
                ticket=ticket,
                agent=agent,
                event_type=HistoryEventType.ticket_created,
                description=f"Ticket criado por {agent.name} a partir de mensagem pendente",
            )
        )
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def ignore_pending_message(self, pending_id: int, agent: Agent) -> bool:
        pending = self.db.get(PendingTicketMessage, pending_id)
        if pending is None:
            return False
        if pending.status != "pending":
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Mensagem pendente já foi tratada",
            )
        pending.status = "ignored"
        self.db.commit()
        return True

    def _copy_pending_to_ticket(
        self,
        pending: PendingTicketMessage,
        ticket: Ticket,
    ) -> TicketMessage:
        saved = TicketMessage(
            ticket=ticket,
            direction=MessageDirection.inbound,
            content=pending.content,
            media_type=pending.media_type,
            media_url=pending.media_url,
            media_mime_type=pending.media_mime_type,
            media_storage_key=pending.media_storage_key,
            external_message_id=pending.external_message_id,
            sender=pending.sender,
        )
        self.db.add(saved)
        return saved
