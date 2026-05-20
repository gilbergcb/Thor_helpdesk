from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_agent, require_admin
from app.core.database import get_db
from app.models.support import Agent
from app.models.ticket import Ticket
from app.schemas.ticket import (
    AssignTicketRequest,
    KanbanColumn,
    ReplyTicketRequest,
    TicketDetail,
    TicketMessageRead,
    TicketRead,
    TicketUpdateRequest,
    UpdateTicketStatusRequest,
)
from app.services.tickets import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/kanban", response_model=list[KanbanColumn])
def kanban(
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> list[KanbanColumn]:
    columns = TicketService(db).kanban(viewer=agent)
    return [KanbanColumn(status=status_key, tickets=tickets) for status_key, tickets in columns.items()]


@router.get("/{ticket_id}", response_model=TicketDetail)
def detail(
    ticket_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(get_current_agent)],
) -> TicketDetail:
    ticket = TicketService(db).get_detail(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("/{ticket_id}/assign", response_model=TicketRead)
def assign(
    ticket_id: int,
    payload: AssignTicketRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketRead:
    ticket = TicketService(db).assign(ticket_id, agent, payload.agent_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket or agent not found")
    return ticket


@router.patch("/{ticket_id}/status", response_model=TicketRead)
def change_status(
    ticket_id: int,
    payload: UpdateTicketStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketRead:
    ticket = TicketService(db).change_status(ticket_id, payload.status, agent)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("/{ticket_id}/reply", response_model=TicketMessageRead)
async def reply(
    ticket_id: int,
    payload: ReplyTicketRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketMessageRead:
    message = await TicketService(db).reply(ticket_id, payload.message, agent)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return message


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> TicketRead:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(ticket, key, value)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> None:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    db.delete(ticket)
    db.commit()
