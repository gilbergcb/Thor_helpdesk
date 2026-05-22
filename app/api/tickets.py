import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_agent, require_admin
from app.core.database import get_db
from app.core.tenant import check_ticket_access
from app.models.support import Agent
from app.models.ticket import Ticket, TicketMessage, TicketMessageAttachment
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
from app.services.media_storage import resolve_storage_path
from app.services.tickets import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/kanban", response_model=list[KanbanColumn])
def kanban(
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
    only_mine: bool = False,
) -> list[KanbanColumn]:
    columns = TicketService(db).kanban(viewer=agent, only_mine=only_mine)
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
    request: Request,
    ticket_id: int,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketDetail:
    ticket = TicketService(db).get_detail(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    check_ticket_access(agent, ticket, action="detail", request=request)
    return ticket


@router.post("/{ticket_id}/assign", response_model=TicketRead)
async def assign(
    request: Request,
    ticket_id: int,
    payload: AssignTicketRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketRead:
    # F-05: checa antes de mutar (load_only Ticket por id).
    pre = db.get(Ticket, ticket_id)
    if pre is not None:
        check_ticket_access(agent, pre, action="assign", request=request)
    ticket = await TicketService(db).assign(ticket_id, agent, payload.agent_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket or agent not found",
        )
    return ticket


@router.patch("/{ticket_id}/status", response_model=TicketRead)
async def change_status(
    request: Request,
    ticket_id: int,
    payload: UpdateTicketStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketRead:
    pre = db.get(Ticket, ticket_id)
    if pre is not None:
        check_ticket_access(agent, pre, action="change_status", request=request)
    ticket = await TicketService(db).change_status(ticket_id, payload.status, agent)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("/{ticket_id}/reply", response_model=TicketMessageRead)
async def reply(
    request: Request,
    ticket_id: int,
    payload: ReplyTicketRequest,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> TicketMessageRead:
    pre = db.get(Ticket, ticket_id)
    if pre is not None:
        check_ticket_access(agent, pre, action="reply", request=request)
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


# ----------------------------------------------------------------------------
# Anexos (Fase C — atendente vê arquivos enviados via portal público).
# Rota separada de /media/<message_id> porque attachments tem PK propria
# em ticket_message_attachments. JWT obrigatorio + tenant check via
# ticket da TicketMessage dona do anexo.
# Path `/attachments/{id}` nao colide com `/{ticket_id}` porque int converter
# do FastAPI rejeita "attachments" como ticket_id.
# ----------------------------------------------------------------------------


@router.get("/attachments/{attachment_id}")
def get_ticket_attachment(
    request: Request,
    attachment_id: int,
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> FileResponse:
    """Serve um anexo de TicketMessage para o atendente autenticado.

    Validações em cadeia:
      1. Agent ativo (Depends(get_current_agent)).
      2. Attachment existe e tem mensagem/ticket associado.
      3. Tenant: atendente só vê tickets atribuídos a ele ou pool —
         delegado a check_ticket_access (F-05, modo audit/enforce).
    Qualquer falha → 404 sem revelar existência."""
    row = db.scalar(
        select(TicketMessageAttachment, TicketMessage)
        .join(TicketMessage, TicketMessage.id == TicketMessageAttachment.ticket_message_id)
        .where(TicketMessageAttachment.id == attachment_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anexo não encontrado")
    # `row` é o TicketMessageAttachment; pegamos o ticket via relacionamento.
    msg = db.get(TicketMessage, row.ticket_message_id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anexo órfão")
    ticket = db.get(Ticket, msg.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket ausente")
    check_ticket_access(agent, ticket, action="attachment.read", request=request)

    path = resolve_storage_path(row.storage_key)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo ausente")

    inline_mimes = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
    media_type = row.mime_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    headers: dict[str, str] = {}
    if media_type not in inline_mimes:
        safe_name = row.original_filename or f"anexo-{row.id}"
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
    return FileResponse(path, media_type=media_type, headers=headers)
