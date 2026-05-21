"""F-05 / Phase 4.1 — tenant isolation guard para /tickets/*.

Hoje qualquer atendente acessa qualquer ticket. Regra-alvo (após flip):
  - administrador / supervisor: veem tudo.
  - atendente: vê apenas tickets onde assigned_agent_id == agent.id
    OU assigned_agent_id IS NULL (pool de abertos).

Em modo audit (default), o helper NÃO bloqueia — só loga violações
para coletar evidência durante a janela de 7 dias. Após audit limpo,
flip SECURITY_TENANT_ISOLATION=enforce e atendentes recebem 403/404.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.security_flags import FlagMode, flag_mode
from app.models.enums import AgentRole
from app.models.support import Agent
from app.models.ticket import Ticket

_audit = logging.getLogger("security.tenant")


def _is_violation(agent: Agent, ticket: Ticket) -> bool:
    """Retorna True se atendente está acessando ticket fora do escopo."""
    if agent.role in (AgentRole.administrador, AgentRole.supervisor):
        return False
    # atendente
    if ticket.assigned_agent_id is None:
        return False  # pool de abertos é compartilhado
    return ticket.assigned_agent_id != agent.id


def check_ticket_access(
    agent: Agent,
    ticket: Ticket,
    action: str,
    request: Request | None = None,
) -> None:
    """Aplica SECURITY_TENANT_ISOLATION.

    - off    : no-op.
    - audit  : loga violação, permite.
    - enforce: HTTPException 404 (não revela existência).
    """
    mode = flag_mode(get_settings().security_tenant_isolation)
    if mode is FlagMode.OFF:
        return
    if not _is_violation(agent, ticket):
        return

    ip = None
    if request is not None and request.client is not None:
        ip = request.client.host

    _audit.warning(
        "tenant.access.violation action=%s actor_id=%s actor_role=%s "
        "ticket_id=%s ticket_client_id=%s ticket_assigned_to=%s ip=%s mode=%s",
        action, agent.id, agent.role.value,
        ticket.id, ticket.client_id, ticket.assigned_agent_id, ip, mode.value,
    )

    if mode is FlagMode.ENFORCE:
        # 404 (not 403) para não vazar existência do ticket.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
