"""F-06 / Phase 2.1 — bootstrap idempotente do primeiro admin.

Roda no CMD do container backend (antes do uvicorn). Comportamento:
- Se já existe QUALQUER agente com role=administrador → no-op (sai 0).
- Caso contrário, lê INITIAL_ADMIN_EMAIL e INITIAL_ADMIN_PASSWORD do env.
  - Se faltar qualquer um → log WARN e sai 0 (não bloqueia startup).
  - Se ambos presentes → cria admin com must_change_password=True.

Em produção existente, há admin → no-op. Em deploy novo, opera-dor define
as duas envs antes do primeiro `docker compose up`.
"""
from __future__ import annotations

import logging
import os
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.enums import AgentRole
from app.models.support import Agent

logging.basicConfig(level=logging.INFO, format="[bootstrap_admin] %(message)s")
log = logging.getLogger("bootstrap_admin")


def main() -> int:
    email = (os.environ.get("INITIAL_ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("INITIAL_ADMIN_PASSWORD") or ""

    db = SessionLocal()
    try:
        existing = db.scalar(
            select(Agent).where(Agent.role == AgentRole.administrador).limit(1)
        )
        if existing is not None:
            log.info("admin já existe (id=%s) — no-op", existing.id)
            return 0

        if not email or not password:
            log.warning(
                "nenhum admin encontrado E INITIAL_ADMIN_EMAIL/PASSWORD nao setados — "
                "pulando bootstrap (defina as envs e reinicie para criar o primeiro admin)"
            )
            return 0

        if len(password) < 12:
            log.error("INITIAL_ADMIN_PASSWORD precisa ter >=12 chars; abortando")
            return 1

        agent = Agent(
            name="Administrador",
            email=email,
            password_hash=get_password_hash(password),
            is_active=True,
            role=AgentRole.administrador,
            must_change_password=True,
        )
        db.add(agent)
        db.commit()
        log.info("admin criado: %s (must_change_password=True)", email)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
