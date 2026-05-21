"""F-04 / Phase 2.2 — re-cifra TODOS os client_access_credentials usando a
chave nova (VAULT_SECRET_KEY), aceitando ciphertexts antigos via
VAULT_SECRET_KEY_OLD se necessário.

Uso (dentro do container backend):
    docker compose exec backend python -m scripts.security.re_encrypt_credentials

Pré-requisitos:
    - Backup do DB feito (db.sql.gz da Fase 0 ou pg_dump fresco).
    - .env contém VAULT_SECRET_KEY (nova) e VAULT_SECRET_KEY_OLD (antiga).
    - Após rodar e validar, remover VAULT_SECRET_KEY_OLD do .env e restart.

Idempotente: se um registro já está na chave nova, decrypt cai no caminho
"new", encrypt re-grava com new, no-op funcional.
"""
from __future__ import annotations

import sys

from app.core.database import SessionLocal
from app.core.security import decrypt_secret, encrypt_secret
from app.models.client import ClientAccessCredential


def main() -> int:
    db = SessionLocal()
    try:
        rows = db.query(ClientAccessCredential).all()
        total = len(rows)
        ok = 0
        failed: list[int] = []
        for row in rows:
            try:
                plain_secret = decrypt_secret(row.secret_encrypted)
                plain_notes = decrypt_secret(row.notes_encrypted)
            except Exception as exc:  # noqa: BLE001
                print(f"[FAIL id={row.id}] decrypt: {exc!r}")
                failed.append(row.id)
                continue

            row.secret_encrypted = encrypt_secret(plain_secret) or ""
            row.notes_encrypted = encrypt_secret(plain_notes)
            ok += 1

        if failed:
            db.rollback()
            print(f"\nABORT: {len(failed)}/{total} falharam ao decifrar: {failed}")
            print("Nenhuma alteração foi gravada. Cheque VAULT_SECRET_KEY_OLD.")
            return 2

        db.commit()
        print(f"\nOK: re-cifrados {ok}/{total} credenciais com a chave nova.")
        print("Próximo passo: remover VAULT_SECRET_KEY_OLD do .env e restart backend.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
