from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_agent, get_current_agent_allow_password_change
from app.core.database import get_db
from app.core.ratelimit import limiter, ratelimit_active
from app.core.security import (
    decode_access_token_full,
    decrypt_secret,
    encrypt_secret,
    generate_totp_secret,
    totp_provisioning_uri,
    verify_totp_code,
)
from app.models.security import RevokedToken
from app.models.support import Agent
from app.schemas.auth import (
    AgentMe,
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    TotpDisableRequest,
    TotpEnableRequest,
    TotpSetupResponse,
)
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


@router.post("/totp/setup", response_model=TotpSetupResponse)
def setup_totp(
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> TotpSetupResponse:
    if agent.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA ja configurado para este usuario",
        )
    secret = generate_totp_secret()
    agent.totp_secret_encrypted = encrypt_secret(secret)
    db.commit()
    return TotpSetupResponse(
        secret=secret,
        provisioning_uri=totp_provisioning_uri(secret, agent.email),
    )


@router.post("/totp/enable", response_model=AgentMe)
def enable_totp(
    payload: TotpEnableRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> Agent:
    secret = decrypt_secret(agent.totp_secret_encrypted)
    if not secret or not verify_totp_code(secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo 1Password invalido",
        )
    agent.totp_enabled = True
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/totp/disable", response_model=AgentMe)
def disable_totp(
    payload: TotpDisableRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> Agent:
    secret = decrypt_secret(agent.totp_secret_encrypted)
    if not agent.totp_enabled or not secret or not verify_totp_code(secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo 1Password invalido",
        )
    agent.totp_enabled = False
    agent.totp_secret_encrypted = None
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    agent: Annotated[Agent, Depends(get_current_agent_allow_password_change)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """F-12 parcial: insere o `jti` em revoked_tokens. Próximas requisições
    com o mesmo token retornam 401. Tokens antigos (sem jti) não podem ser
    revogados — expirarão naturalmente em access_token_expire_minutes."""
    decoded = decode_access_token_full(credentials.credentials)
    if decoded is None or decoded.jti is None:
        # token legado sem jti — nada a revogar; logout silencioso (frontend
        # apaga o token local de qualquer jeito).
        return None
    # idempotente: se já está revogado, no-op.
    if db.get(RevokedToken, decoded.jti) is not None:
        return None
    expires_at = decoded.expires_at or (datetime.now(UTC) + timedelta(hours=24))
    db.add(RevokedToken(jti=decoded.jti, expires_at=expires_at, agent_id=agent.id))
    db.commit()
    return None
