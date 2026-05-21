import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.enums import HistoryEventType, TicketStatus
from app.models.ticket import Ticket, TicketHistory
from app.services.public_links import PublicTicketLinkService

logger = logging.getLogger(__name__)


def close_stale_waiting_customer_tickets(
    db: Session,
    now: datetime | None = None,
) -> int:
    settings = get_settings()
    reference = now or datetime.now(UTC)
    cutoff = reference - timedelta(hours=settings.waiting_customer_auto_close_hours)
    tickets = list(
        db.scalars(
            select(Ticket)
            .where(
                Ticket.status == TicketStatus.aguardando_cliente,
                Ticket.updated_at <= cutoff,
            )
            .options(selectinload(Ticket.public_links))
        )
    )
    for ticket in tickets:
        ticket.status = TicketStatus.fechado
        ticket.closed_at = reference
        PublicTicketLinkService(db).revoke_for_ticket(ticket)
        db.add(
            TicketHistory(
                ticket=ticket,
                event_type=HistoryEventType.status_changed,
                description=(
                    "Ticket fechado automaticamente após "
                    f"{settings.waiting_customer_auto_close_hours}h aguardando cliente"
                ),
            )
        )
    if tickets:
        db.commit()
    return len(tickets)


def close_stale_waiting_customer_tickets_once() -> int:
    with SessionLocal() as db:
        return close_stale_waiting_customer_tickets(db)


async def waiting_customer_auto_close_loop() -> None:
    settings = get_settings()
    interval = max(60, settings.waiting_customer_auto_close_interval_seconds)
    while True:
        try:
            closed = await asyncio.to_thread(close_stale_waiting_customer_tickets_once)
            if closed:
                logger.info("Fechados automaticamente %s tickets aguardando cliente", closed)
        except Exception:
            logger.exception("Falha ao fechar tickets aguardando cliente automaticamente")
        await asyncio.sleep(interval)
