from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import HistoryEventType, MessageDirection
from app.models.ticket import TicketHistory, TicketMessage
from app.schemas.public import PublicTicketMessageCreate, PublicTicketRead
from app.services.public_links import PublicTicketLinkService

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/tickets/{token}", response_model=PublicTicketRead)
def get_public_ticket(
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> PublicTicketRead:
    link = PublicTicketLinkService(db).get_valid_link(token)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link inválido ou expirado",
        )
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


@router.post("/tickets/{token}/messages", response_model=PublicTicketRead)
def create_public_ticket_message(
    token: str,
    payload: PublicTicketMessageCreate,
    db: Annotated[Session, Depends(get_db)],
) -> PublicTicketRead:
    link = PublicTicketLinkService(db).get_valid_link(token)
    if link is None:
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
    return get_public_ticket(token, db)
