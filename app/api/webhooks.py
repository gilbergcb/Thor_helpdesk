from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.webhook import WebhookResult, ZApiWebhookPayload
from app.services.webhook import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/zapi", response_model=WebhookResult)
async def zapi_webhook(
    payload: ZApiWebhookPayload,
    db: Annotated[Session, Depends(get_db)],
) -> WebhookResult:
    return await WebhookService(db).process_message(payload)
