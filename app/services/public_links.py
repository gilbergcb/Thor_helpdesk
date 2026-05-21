from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import generate_public_ticket_token, hash_public_token
from app.models.client import ClientEmployee
from app.models.enums import TicketStatus
from app.models.ticket import Ticket, TicketPublicLink
from app.models.whatsapp import WhatsAppUser


class PublicTicketLinkService:
    def __init__(self, db: Session):
        self.db = db

    def create_for_ticket(self, ticket: Ticket) -> str:
        token = generate_public_ticket_token()
        self.db.add(TicketPublicLink(ticket=ticket, token_hash=hash_public_token(token)))
        return token

    def public_url(self, token: str) -> str:
        base_url = str(get_settings().public_app_url).rstrip("/")
        return f"{base_url}/t/{token}"

    def get_valid_link(self, token: str) -> TicketPublicLink | None:
        now = datetime.now(UTC)
        link = self.db.scalar(
            select(TicketPublicLink)
            .where(TicketPublicLink.token_hash == hash_public_token(token))
            .options(
                joinedload(TicketPublicLink.ticket).joinedload(Ticket.client),
                joinedload(TicketPublicLink.ticket).joinedload(Ticket.whatsapp_group),
                joinedload(TicketPublicLink.ticket)
                .joinedload(Ticket.requester)
                .joinedload(WhatsAppUser.employee)
                .joinedload(ClientEmployee.role),
                joinedload(TicketPublicLink.ticket).joinedload(Ticket.assigned_agent),
                joinedload(TicketPublicLink.ticket).selectinload(Ticket.messages),
            )
        )
        if link is None or link.revoked_at is not None:
            return None
        if link.expires_at is not None and link.expires_at <= now:
            return None
        if link.ticket.status == TicketStatus.fechado:
            return None
        link.last_access_at = now
        self.db.commit()
        return link

    def revoke_for_ticket(self, ticket: Ticket) -> None:
        now = datetime.now(UTC)
        for link in ticket.public_links:
            if link.revoked_at is None:
                link.revoked_at = now
