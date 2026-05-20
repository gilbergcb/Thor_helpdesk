import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.ticket import TicketMessage
from app.services.media_storage import resolve_storage_path

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{message_id}")
def get_message_media(
    message_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    message = db.get(TicketMessage, message_id)
    if message is None or not message.media_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    path = resolve_storage_path(message.media_storage_key)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    media_type = message.media_mime_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
