import logging
import mimetypes
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.public_links import public_token_fingerprint, validate_public_ticket_token
from app.core.ratelimit import limiter
from app.models.enums import HistoryEventType, MessageDirection
from app.models.ticket import (
    TicketHistory,
    TicketMessage,
    TicketMessageAttachment,
    TicketPublicLink,
)
from app.schemas.public import (
    PublicTicketAttachmentRead,
    PublicTicketMessageRead,
    PublicTicketRead,
)
from app.services.media_storage import (
    UploadValidationError,
    resolve_storage_path,
    save_uploaded_file,
)
from app.services.public_links import PublicTicketLinkService

router = APIRouter(prefix="/public", tags=["public"])
logger = logging.getLogger("security.public_links")
upload_logger = logging.getLogger("security.public_uploads")

_FILENAME_SANITIZE = re.compile(r"[^\w.\- ]+")


def _public_link_guard_active() -> bool:
    val = (get_settings().security_public_link_guard or "on").strip().lower()
    return val not in {"off", "false", "0", "no"}


def _public_ticket_get_rate_limit() -> str:
    return "60/minute" if _public_link_guard_active() else "10000/minute"


def _public_ticket_post_rate_limit() -> str:
    return "10/minute" if _public_link_guard_active() else "10000/minute"


def _public_ticket_upload_rate_limit() -> str:
    """Upload com anexos: limite mais agressivo (cada request consome storage)."""
    return "3/minute" if _public_link_guard_active() else "10000/minute"


def _validate_public_token(token: str) -> None:
    try:
        validate_public_ticket_token(token)
        return
    except HTTPException:
        logger.warning("public_ticket.invalid_token_format %s", public_token_fingerprint(token))
        raise


def _sanitize_filename(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    # nunca confia no nome do user — pega só basename, remove path traversal,
    # corta caracteres não-imprimíveis. Limita 100 chars.
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = _FILENAME_SANITIZE.sub("_", name)
    return name[:100] or None


def _build_attachment_url(token: str, attachment_id: int) -> str:
    return f"/api/v1/public/tickets/{token}/attachments/{attachment_id}"


def _serialize_message(message: TicketMessage, token: str) -> PublicTicketMessageRead:
    attachments = [
        PublicTicketAttachmentRead(
            id=a.id,
            mime_type=a.mime_type,
            byte_size=a.byte_size,
            original_filename=a.original_filename,
            source=a.source,
            url=_build_attachment_url(token, a.id),
        )
        for a in message.attachments
    ]
    return PublicTicketMessageRead(
        id=message.id,
        direction=message.direction,
        content=message.content,
        media_type=message.media_type,
        media_storage_key=message.media_storage_key,
        attachments=attachments,
        created_at=message.created_at,
    )


def _public_ticket_read(link, token: str) -> PublicTicketRead:
    ticket = link.ticket
    return PublicTicketRead(
        protocol=ticket.protocol,
        title=ticket.title,
        status=ticket.status,
        client_name=ticket.client.name,
        group_name=ticket.whatsapp_group.name,
        requester_name=ticket.requester.name if ticket.requester else None,
        assigned_agent=ticket.assigned_agent,
        messages=[_serialize_message(m, token) for m in ticket.messages],
    )


def _hourly_upload_bytes(db: Session, ticket_id: int) -> int:
    """Somatório de bytes uploaded para anexos source=public_portal no ticket
    nas últimas 60 minutos. Base para enforcement de quota horária."""
    since = datetime.now(UTC) - timedelta(hours=1)
    total = db.scalar(
        select(func.coalesce(func.sum(TicketMessageAttachment.byte_size), 0))
        .join(TicketMessage, TicketMessage.id == TicketMessageAttachment.ticket_message_id)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessageAttachment.source == "public_portal",
            TicketMessageAttachment.created_at >= since,
        )
    )
    return int(total or 0)


# ============================================================================
# Rotas
# ============================================================================


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
    return _public_ticket_read(link, token)


@router.post("/tickets/{token}/messages", response_model=PublicTicketRead)
@limiter.limit(_public_ticket_upload_rate_limit)
def create_public_ticket_message(
    request: Request,
    token: str,
    db: Annotated[Session, Depends(get_db)],
    message: Annotated[str, Form()] = "",
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> PublicTicketRead:
    """Aceita multipart/form-data com:
      - `message` (Form, opcional se houver anexo): texto da mensagem.
      - `files` (File, opcional se houver texto): até N arquivos.

    Validações: MIME via libmagic, tamanho por arquivo, quantidade por
    request, quota horária acumulada por ticket. Falhas validadas retornam
    400/413/415 com mensagem clara; falhas internas viram 500."""
    settings = get_settings()
    _validate_public_token(token)
    link = PublicTicketLinkService(db).get_valid_link(token)
    if link is None:
        logger.warning(
            "public_ticket.message.invalid_or_expired %s", public_token_fingerprint(token)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link inválido ou expirado"
        )

    text = (message or "").strip()
    files = [f for f in (files or []) if f is not None and (f.filename or f.size)]
    if not text and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envie uma mensagem ou pelo menos um arquivo",
        )

    if len(text) > 4000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mensagem maior que 4000 caracteres",
        )

    max_files = settings.public_upload_max_files_per_request
    if len(files) > max_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximo de {max_files} arquivos por envio",
        )

    # Quota horaria pre-check (rejeita antes de gravar bytes no disco).
    max_per_file = settings.public_upload_max_bytes
    hourly_quota = settings.public_upload_quota_bytes_per_hour
    consumed = _hourly_upload_bytes(db, link.ticket_id)

    ip = request.client.host if request.client else None
    token_fp = public_token_fingerprint(token)

    # Lê todos os bytes na memória (cap 15MB × 3 = 45MB max — aceitável).
    raw_files: list[tuple[bytes, str | None, str | None]] = []
    for upload in files:
        raw = upload.file.read()
        if len(raw) > max_per_file:
            upload_logger.warning(
                "public_upload.reject reason=too_large size=%s token=%s ip=%s",
                len(raw), token_fp, ip,
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Arquivo excede {max_per_file // (1024 * 1024)} MB",
            )
        raw_files.append((raw, upload.content_type, upload.filename))

    request_total = sum(len(r) for r, _, _ in raw_files)
    if consumed + request_total > hourly_quota:
        upload_logger.warning(
            "public_upload.reject reason=hourly_quota consumed=%s request=%s "
            "quota=%s token=%s ip=%s",
            consumed, request_total, hourly_quota, token_fp, ip,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quota de upload de {hourly_quota // (1024 * 1024)} MB/hora atingida",
        )

    # Persistencia + criacao da TicketMessage + Attachments numa transacao.
    ticket = link.ticket
    msg = TicketMessage(
        ticket=ticket,
        direction=MessageDirection.inbound,
        content=text or "[anexo]",
        sender=ticket.requester,
    )
    db.add(msg)
    db.flush()  # garante msg.id antes de criar attachments

    saved_attachments: list[tuple[int, str, int]] = []
    try:
        for raw, declared_mime, filename in raw_files:
            try:
                storage_key, detected_mime, byte_size = save_uploaded_file(
                    raw, declared_mime, max_bytes=max_per_file
                )
            except UploadValidationError as exc:
                upload_logger.warning(
                    "public_upload.reject reason=validation msg=%s token=%s ip=%s",
                    exc, token_fp, ip,
                )
                # Rollback explicito da TicketMessage criada acima.
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
                ) from exc

            att = TicketMessageAttachment(
                ticket_message_id=msg.id,
                storage_key=storage_key,
                mime_type=detected_mime,
                byte_size=byte_size,
                original_filename=_sanitize_filename(filename),
                source="public_portal",
            )
            db.add(att)
            db.flush()
            saved_attachments.append((att.id, detected_mime, byte_size))

        db.add(
            TicketHistory(
                ticket=ticket,
                event_type=HistoryEventType.message_received,
                description=(
                    "Mensagem recebida pelo portal público do cliente"
                    + (f" (anexos: {len(saved_attachments)})" if saved_attachments else "")
                ),
            )
        )
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise

    upload_logger.info(
        "public_upload.ok ticket_id=%s msg_id=%s attachments=%s total_bytes=%s "
        "token=%s ip=%s",
        ticket.id, msg.id, len(saved_attachments),
        sum(s for _, _, s in saved_attachments), token_fp, ip,
    )
    # recarrega link para refletir nova mensagem na resposta
    db.refresh(link.ticket)
    return _public_ticket_read(link, token)


@router.get("/tickets/{token}/attachments/{attachment_id}")
@limiter.limit(_public_ticket_get_rate_limit)
def get_public_ticket_attachment(
    request: Request,
    token: str,
    attachment_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    """Serve um anexo de mensagem do portal publico.
    Validacoes em cadeia:
      1. Formato do token.
      2. Link valido (nao expirado, nao revogado, ticket nao fechado).
      3. Attachment pertence a uma TicketMessage do mesmo ticket do link.
    Qualquer falha -> 404 sem revelar existencia do recurso."""
    _validate_public_token(token)
    link = PublicTicketLinkService(db).get_valid_link(token)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link inválido ou expirado"
        )
    att = db.scalar(
        select(TicketMessageAttachment)
        .join(TicketMessage, TicketMessage.id == TicketMessageAttachment.ticket_message_id)
        .where(
            TicketMessageAttachment.id == attachment_id,
            TicketMessage.ticket_id == link.ticket_id,
        )
    )
    if att is None:
        logger.warning(
            "public_attachment.not_found token=%s attachment_id=%s",
            public_token_fingerprint(token), attachment_id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anexo não encontrado")

    path = resolve_storage_path(att.storage_key)
    if path is None:
        logger.error(
            "public_attachment.path_missing attachment_id=%s storage_key=%s",
            att.id, att.storage_key,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo ausente")

    # Forca download para tipos nao renderizaveis (defesa contra inline render
    # de payloads com Content-Type relaxado). Imagens e PDF abrem inline.
    inline_mimes = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
    media_type = att.mime_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    headers: dict[str, str] = {}
    if media_type not in inline_mimes:
        safe_name = att.original_filename or f"anexo-{att.id}"
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'

    return FileResponse(path, media_type=media_type, headers=headers)
