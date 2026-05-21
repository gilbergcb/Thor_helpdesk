from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token_full
from app.models.enums import AgentRole
from app.models.security import RevokedToken
from app.models.support import Agent

bearer_scheme = HTTPBearer()


def get_current_agent_allow_password_change(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Agent:
    decoded = decode_access_token_full(credentials.credentials)
    if decoded is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    # F-12 parcial: rejeita JWT cujo jti foi revogado via /auth/logout.
    if decoded.jti is not None and db.get(RevokedToken, decoded.jti) is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
    agent = db.get(Agent, int(decoded.subject))
    if agent is None or not agent.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive agent")
    return agent


def get_current_agent(
    agent: Annotated[Agent, Depends(get_current_agent_allow_password_change)],
) -> Agent:
    if agent.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )
    return agent


def require_roles(*roles: AgentRole) -> Callable[..., Agent]:
    allowed = set(roles)

    def _dep(agent: Annotated[Agent, Depends(get_current_agent)]) -> Agent:
        if agent.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado para o seu perfil",
            )
        return agent

    return _dep


require_admin = require_roles(AgentRole.administrador)
require_supervisor_or_admin = require_roles(AgentRole.supervisor, AgentRole.administrador)
