from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_agent_allow_password_change
from app.core.database import get_db
from app.models.support import Agent
from app.schemas.auth import AgentMe, ChangePasswordRequest, LoginRequest, TokenResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
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
def change_password(
    payload: ChangePasswordRequest,
    agent: Annotated[Agent, Depends(get_current_agent_allow_password_change)],
    db: Annotated[Session, Depends(get_db)],
) -> Agent:
    if len(payload.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ter pelo menos 6 caracteres",
        )
    changed = AuthService(db).change_password(agent, payload.current_password, payload.new_password)
    if changed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual inválida",
        )
    return changed
