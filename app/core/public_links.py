import re

from fastapi import HTTPException, status

PUBLIC_TICKET_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def public_token_fingerprint(token: str) -> str:
    if not token:
        return "empty"
    return f"len={len(token)} prefix={token[:6]}"


def validate_public_ticket_token(token: str) -> None:
    if PUBLIC_TICKET_TOKEN_RE.fullmatch(token):
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Link inválido ou expirado",
    )
