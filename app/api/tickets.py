from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_agent, require_admin
from app.core.database import get_db
from app.models.support import Agent
from app.models.ticket import Ticket
from app.schemas.ticket import (
    AssignTicketRequest,
    CreateTicketFromPendingRequest,
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
    return [
        KanbanColumn(status=status_key, tickets=tickets)
        for status_key, tickets in columns.items()
    ]


@router.post("/pending/{pending_id}/link/{ticket_id}", response_model=TicketMessageRead)
def link_pending_message(
    pending_id: int,
    ticket_id: int,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketMessageRead:
    message = TicketService(db).link_pending_message(pending_id, ticket_id, agent)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mensagem ou ticket não encontrado",
        )
    return message


@router.post("/pending/{pending_id}/create-ticket", response_model=TicketRead)
def create_ticket_from_pending(
    pending_id: int,
    payload: CreateTicketFromPendingRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketRead:
    ticket = TicketService(db).create_ticket_from_pending(
        pending_id,
        agent,
        title=payload.title,
        description=payload.description,
    )
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mensagem pendente não encontrada",
        )
    return ticket


@router.post("/pending/{pending_id}/ignore", status_code=status.HTTP_204_NO_CONTENT)
def ignore_pending_message(
    pending_id: int,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> None:
    ignored = TicketService(db).ignore_pending_message(pending_id, agent)
    if not ignored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mensagem pendente não encontrada",
        )


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
async def assign(
    ticket_id: int,
    payload: AssignTicketRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketRead:
    ticket = await TicketService(db).assign(ticket_id, agent, payload.agent_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket or agent not found",
        )
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
