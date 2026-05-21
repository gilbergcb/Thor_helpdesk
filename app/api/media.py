import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.security_flags import FlagMode, audit_log, flag_mode
from app.models.support import Agent
from app.models.ticket import PendingTicketMessage, TicketMessage
from app.services.media_storage import resolve_storage_path

router = APIRouter(prefix="/media", tags=["media"])


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def media_auth_guard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Guard SECURITY_MEDIA_AUTH (F-01).

    audit  : loga acesso sem token válido mas permite (default).
    enforce: exige token JWT válido de Agent ativo.
    off    : sem checagem.
    """
    settings = get_settings()
    mode = flag_mode(settings.security_media_auth)
    if mode is FlagMode.OFF:
        return

    token = _extract_bearer(request)
    reason: str | None = None
    if not token:
        reason = "missing_token"
    else:
        subject = decode_access_token(token)
        if subject is None:
            reason = "invalid_token"
        else:
            agent = db.get(Agent, int(subject))
            if agent is None or not agent.is_active:
                reason = "inactive_agent"

    if reason is None:
        return

    if mode is FlagMode.AUDIT:
        audit_log(
            "media.auth",
            reason=reason,
            path=request.url.path,
            ip=request.client.host if request.client else None,
        )
        return

    # ENFORCE
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


@router.get("/pending/{message_id}")
def get_pending_message_media(
    message_id: int,
    db: Annotated[Session, Depends(get_db)],
    _guard: Annotated[None, Depends(media_auth_guard)],
) -> FileResponse:
    message = db.get(PendingTicketMessage, message_id)
    if message is None or not message.media_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    path = resolve_storage_path(message.media_storage_key)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    media_type = (
        message.media_mime_type
        or mimetypes.guess_type(str(path))[0]
        or "application/octet-stream"
    )
    return FileResponse(path, media_type=media_type)


@router.get("/{message_id}")
def get_message_media(
    message_id: int,
    db: Annotated[Session, Depends(get_db)],
    _guard: Annotated[None, Depends(media_auth_guard)],
) -> FileResponse:
    message = db.get(TicketMessage, message_id)
    if message is None or not message.media_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    path = resolve_storage_path(message.media_storage_key)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    media_type = (
        message.media_mime_type
        or mimetypes.guess_type(str(path))[0]
        or "application/octet-stream"
    )
    return FileResponse(path, media_type=media_type)
