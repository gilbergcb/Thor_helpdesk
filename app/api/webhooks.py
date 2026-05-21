import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security_flags import FlagMode, audit_log, flag_mode
from app.schemas.webhook import WebhookResult, ZApiWebhookPayload
from app.services.webhook import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def zapi_token_guard(request: Request) -> None:
    """Guard SECURITY_WEBHOOK_HMAC (F-02).

    Compara header `Client-Token` com `settings.zapi_client_token` (compare constante).
    audit  : loga discrepância e permite.
    enforce: 401 se ausente/diferente.
    """
    settings = get_settings()
    mode = flag_mode(settings.security_webhook_hmac)
    if mode is FlagMode.OFF:
        return

    expected = settings.zapi_client_token
    received = request.headers.get("client-token") or request.headers.get("Client-Token")

    reason: str | None = None
    if not expected:
        reason = "server_token_unset"
    elif not received:
        reason = "missing_client_token"
    elif not hmac.compare_digest(received, expected):
        reason = "client_token_mismatch"

    if reason is None:
        return

    if mode is FlagMode.AUDIT:
        audit_log(
            "webhook.zapi",
            reason=reason,
            ip=request.client.host if request.client else None,
            has_header=bool(received),
        )
        return

    # ENFORCE
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client token")


@router.post("/zapi", response_model=WebhookResult)
async def zapi_webhook(
    payload: ZApiWebhookPayload,
    db: Annotated[Session, Depends(get_db)],
    _guard: Annotated[None, Depends(zapi_token_guard)],
) -> WebhookResult:
    return await WebhookService(db).process_message(payload)
