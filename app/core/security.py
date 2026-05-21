import base64
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.fernet import Fernet, InvalidToken
from jwt import PyJWTError
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def generate_reveal_token() -> str:
    return secrets.token_urlsafe(24)


def generate_public_ticket_token() -> str:
    return secrets.token_urlsafe(32)


def hash_public_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _fernet_for(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _vault() -> Fernet:
    settings = get_settings()
    secret = settings.vault_secret_key or settings.jwt_secret_key
    return _fernet_for(secret)


def _vault_old() -> Fernet | None:
    """Phase 2.2: chave antiga aceita só em decifragem durante janela de rotação."""
    settings = get_settings()
    if not settings.vault_secret_key_old:
        return None
    return _fernet_for(settings.vault_secret_key_old)


def encrypt_secret(value: str | None) -> str | None:
    """Sempre cifra com chave atual."""
    if value is None:
        return None
    return _vault().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    """Tenta chave nova primeiro; se setada, cai pra antiga (compat rotação)."""
    if value is None:
        return None
    raw = value.encode("utf-8")
    try:
        return _vault().decrypt(raw).decode("utf-8")
    except InvalidToken:
        old = _vault_old()
        if old is None:
            raise
        return old.decrypt(raw).decode("utf-8")


@dataclass(frozen=True)
class DecodedToken:
    subject: str
    jti: str | None
    expires_at: datetime | None


def create_access_token(subject: str) -> str:
    """F-12 parcial: inclui `jti` (uuid4) para suportar revogação via logout.
    Tokens emitidos pela versão antiga (sem jti) continuam válidos no decode."""
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "exp": expires_at,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Compat: retorna só o subject (rotas antigas)."""
    decoded = decode_access_token_full(token)
    return decoded.subject if decoded else None


def decode_access_token_full(token: str) -> DecodedToken | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except PyJWTError:
        return None
    subject = payload.get("sub")
    if not subject:
        return None
    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=UTC) if isinstance(exp, int | float) else None
    jti = payload.get("jti")
    return DecodedToken(subject=str(subject), jti=str(jti) if jti else None, expires_at=expires_at)
