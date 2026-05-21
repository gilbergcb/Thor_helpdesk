from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_agent_allow_password_change
from app.core.database import get_db
from app.core.ratelimit import limiter, ratelimit_active
from app.models.support import Agent
from app.schemas.auth import AgentMe, ChangePasswordRequest, LoginRequest, TokenResponse
from app.services.auth import AuthService

# F-09: política de senha em troca futura (não invalida senhas atuais).
MIN_PASSWORD_LENGTH = 12

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_rate_limit() -> str:
    return "5/minute" if ratelimit_active() else "10000/minute"


def _change_password_rate_limit() -> str:
    return "5/hour" if ratelimit_active() else "10000/minute"


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_login_rate_limit)
def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    service = AuthService(db)
    agent = service.authenticate(payload.email, payload.password)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return TokenResponse(access_token=service.create_token(agent))


@router.get("/me", response_model=AgentMe)
def me(agent: Annotated[Agent, Depends(get_current_agent_allow_password_change)]) -> Agent:
    return agent


@router.post("/change-password", response_model=AgentMe)
@limiter.limit(_change_password_rate_limit)
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    agent: Annotated[Agent, Depends(get_current_agent_allow_password_change)],
    db: Annotated[Session, Depends(get_db)],
) -> Agent:
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A nova senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres",
        )
    changed = AuthService(db).change_password(agent, payload.current_password, payload.new_password)
    if changed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual inválida",
        )
    return changed
