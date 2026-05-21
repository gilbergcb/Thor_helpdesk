"""F-09 / Phase 2.3 — rate limiting via slowapi.

Backend é in-memory por processo (default do slowapi). Suficiente para
1 worker uvicorn. Se escalar p/ N workers, considerar storage Redis
via `storage_uri="redis://..."`.

Pode ser desligado em runtime via SECURITY_RATELIMIT_LOGIN=off.
"""
from __future__ import annotations

import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.core.config import get_settings

logger = logging.getLogger("security.ratelimit")


def _client_key(request: Request) -> str:
    # Respeita X-Forwarded-For se vier da rede docker (proxy reverso).
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_client_key, default_limits=[], headers_enabled=True)


def ratelimit_active() -> bool:
    """Permite ligar/desligar via flag sem redeploy. on/audit = ativo, off = inativo."""
    val = (get_settings().security_ratelimit_login or "on").strip().lower()
    return val not in {"off", "false", "0", "no"}


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning(
        "ratelimit.block ip=%s path=%s detail=%s",
        _client_key(request),
        request.url.path,
        str(exc.detail),
    )
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Tente novamente em alguns instantes."},
    )
