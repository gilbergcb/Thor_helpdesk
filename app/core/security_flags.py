"""Helpers para feature flags SECURITY_* (modo off/audit/enforce).

Padrão de uso:
    mode = flag_mode(settings.security_media_auth)
    if mode is FlagMode.OFF: return  # nada a checar
    ok = do_check(...)
    if not ok:
        if mode is FlagMode.AUDIT:
            audit_log("media.auth", reason="missing_token", ...)
            return  # NÃO bloqueia
        # ENFORCE
        raise HTTPException(...)
"""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("security.audit")


class FlagMode(str, Enum):
    OFF = "off"
    AUDIT = "audit"
    ENFORCE = "enforce"


def flag_mode(value: str | None) -> FlagMode:
    if not value:
        return FlagMode.AUDIT
    normalized = value.strip().lower()
    try:
        return FlagMode(normalized)
    except ValueError:
        logger.warning("security flag invalid value=%r — defaulting to audit", value)
        return FlagMode.AUDIT


def audit_log(check: str, *, reason: str, **fields: object) -> None:
    """Log estruturado de violação em modo audit (não bloqueia)."""
    extras = " ".join(f"{k}={v!r}" for k, v in fields.items())
    logger.warning("security.audit check=%s reason=%s %s", check, reason, extras)
