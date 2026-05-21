"""F-18 — helper para gravar admin_audit_log a partir das rotas."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.security import AdminAuditLog
from app.models.support import Agent

_log = logging.getLogger("security.admin_audit")


def _payload_hash(payload: Any | None) -> str | None:
    if payload is None:
        return None
    try:
        canonical = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        canonical = repr(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_admin_action(
    db: Session,
    *,
    actor: Agent | None,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    request: Request | None = None,
    payload: Any | None = None,
    commit: bool = True,
) -> None:
    """Grava uma linha em admin_audit_log. Nunca levanta — falhas só logam.

    `commit=False` quando a rota já vai commitar a transação principal e
    quer englobar o audit log atomicamente.
    """
    ip = None
    if request is not None:
        ip = request.headers.get("x-forwarded-for")
        if ip:
            ip = ip.split(",")[0].strip()
        elif request.client is not None:
            ip = request.client.host

    row = AdminAuditLog(
        actor_agent_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        actor_role=actor.role.value if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        payload_hash=_payload_hash(payload),
        source_ip=ip,
    )
    try:
        db.add(row)
        if commit:
            db.commit()
    except Exception as exc:  # noqa: BLE001
        _log.warning("falha ao gravar admin_audit_log action=%s: %s", action, exc)
        if commit:
            db.rollback()
