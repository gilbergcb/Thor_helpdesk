import secrets

import pytest
from fastapi import HTTPException

from app.core.public_links import validate_public_ticket_code, validate_public_ticket_token


def test_generated_public_ticket_token_is_accepted() -> None:
    validate_public_ticket_token(secrets.token_urlsafe(32))


def test_generated_public_ticket_code_is_accepted() -> None:
    validate_public_ticket_code(secrets.token_urlsafe(8))


@pytest.mark.parametrize(
    "token",
    [
        "",
        "' OR 1=1--",
        "abc/def",
        "abc%2Fdef",
        "abc.def",
        "a" * 129,
    ],
)
def test_malformed_public_ticket_token_is_404(token: str) -> None:
    with pytest.raises(HTTPException) as exc:
        validate_public_ticket_token(token)

    assert exc.value.status_code == 404


@pytest.mark.parametrize("code", ["", "abc/def", "abc.def", "a" * 33])
def test_malformed_public_ticket_code_is_404(code: str) -> None:
    with pytest.raises(HTTPException) as exc:
        validate_public_ticket_code(code)

    assert exc.value.status_code == 404
