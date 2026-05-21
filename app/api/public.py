import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.public_links import public_token_fingerprint, validate_public_ticket_token
from app.core.ratelimit import limiter
from app.models.enums import HistoryEventType, MessageDirection
from app.models.ticket import TicketHistory, TicketMessage
from app.schemas.public import PublicTicketMessageCreate, PublicTicketRead
from app.services.public_links import PublicTicketLinkService

router = APIRouter(prefix="/public", tags=["public"])
logger = logging.getLogger("security.public_links")


def _public_link_guard_active() -> bool:
    val = (get_settings().security_public_link_guard or "on").strip().lower()
    return val not in {"off", "false", "0", "no"}


def _public_ticket_get_rate_limit() -> str:
    return "60/minute" if _public_link_guard_active() else "10000/minute"


def _public_ticket_post_rate_limit() -> str:
    return "10/minute" if _public_link_guard_active() else "10000/minute"


def _validate_public_token(token: str) -> None:
    try:
        validate_public_ticket_token(token)
        return
    except HTTPException:
        logger.warning("public_ticket.invalid_token_format %s", public_token_fingerprint(token))
        raise


def _public_ticket_read(link) -> PublicTicketRead:
    ticket = link.ticket
    return PublicTicketRead(
        protocol=ticket.protocol,
        title=ticket.title,
        status=ticket.status,
        client_name=ticket.client.name,
        group_name=ticket.whatsapp_group.name,
        requester_name=ticket.requester.name if ticket.requester else None,
        assigned_agent=ticket.assigned_agent,
        messages=ticket.messages,
    )


@router.get("/tickets/{token}", response_model=PublicTicketRead)
@limiter.limit(_public_ticket_get_rate_limit)
def get_public_ticket(
    request: Request,
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> PublicTicketRead:
    _validate_public_token(token)
    link = PublicTicketLinkService(db).get_valid_link(token)
    if link is None:
        logger.warning("public_ticket.invalid_or_expired %s", public_token_fingerprint(token))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link inválido ou expirado",
        )
    logger.info("public_ticket.view ticket_id=%s", link.ticket_id)
    return _public_ticket_read(link)


@router.post("/tickets/{token}/messages", response_model=PublicTicketRead)
@limiter.limit(_public_ticket_post_rate_limit)
def create_public_ticket_message(
    request: Request,
    token: str,
    payload: PublicTicketMessageCreate,
    db: Annotated[Session, Depends(get_db)],
) -> PublicTicketRead:
    _validate_public_token(token)
    link = PublicTicketLinkService(db).get_valid_link(token)
    if link is None:
        logger.warning(
            "public_ticket.message.invalid_or_expired %s", public_token_fingerprint(token)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link inválido ou expirado",
        )
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mensagem obrigatória")
    ticket = link.ticket
    db.add(
        TicketMessage(
            ticket=ticket,
            direction=MessageDirection.inbound,
            content=message,
            sender=ticket.requester,
        )
    )
    db.add(
        TicketHistory(
            ticket=ticket,
            event_type=HistoryEventType.message_received,
            description="Mensagem recebida pelo portal público do cliente",
        )
    )
    db.commit()
    logger.info("public_ticket.message.created ticket_id=%s", ticket.id)
    return _public_ticket_read(link)
