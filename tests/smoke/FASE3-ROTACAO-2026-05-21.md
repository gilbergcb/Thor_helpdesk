# Fase 3.1 (parcial) F-08 — Rotação de Segredos — 2026-05-21 11:34 GMT-3

**Escopo:** rotação coordenada de `JWT_SECRET_KEY`, `VAULT_SECRET_KEY`, `POSTGRES_PASSWORD`.
**Fora desta janela:** `ZAPI_TOKEN` (próxima janela, requer regenerar no painel Z-API).

## Backups pré-rotação

- `/home/finadmin/backups/helpdesk/pre-rotation-20260521-113007/db.sql.gz` (15K)
- `/home/finadmin/backups/helpdesk/pre-rotation-20260521-113007/.env.enc` (passphrase entregue ao Gilberg em chat)

## Sequência executada

| Etapa | Ação | Resultado |
|---|---|---|
| 1.0 | Backup DB + .env cifrado | ok |
| 1.1 | `ALTER USER helpdesk WITH PASSWORD <novo>` | `ALTER ROLE` |
| 1.2 | Atualizar `POSTGRES_PASSWORD` no `.env` | ok |
| 1.3 | `docker compose up -d backend` (recreate p/ re-interpolar `DATABASE_URL`) | health 200 |
| 2.1 | Setar `VAULT_SECRET_KEY_OLD=<atual>` + `VAULT_SECRET_KEY=<novo>` no `.env` | ok |
| 2.2 | `up -d backend` (dual-key ativo) | health 200 |
| 2.3 | `python -m scripts.security.re_encrypt_credentials` | **38/38 credenciais re-cifradas** |
| 2.4 | Remover `VAULT_SECRET_KEY_OLD` do `.env` | ok |
| 2.5 | `up -d backend` (somente chave nova) | health 200; `_vault_old()` retorna `None`; round-trip OK |
| 3.1 | `JWT_SECRET_KEY=<novo>` no `.env` | ok |
| 3.2 | `up -d backend` | health 200; round-trip do token novo com `jti` OK |

## Incidente

Primeira tentativa de rotação Postgres tinha bug: `python3` subprocess não herdou env var de `source /tmp/new_secrets.env` no mesmo SSH block — `.env` ficou com valor literal `${NEW_PG}`. Backend não conectou ao DB. Corrigido propagando explicitamente `NEW_PG=<value> python3 -c '...'`.

Segunda armadilha: `docker compose restart` **não** re-interpola `${POSTGRES_PASSWORD}` no `environment.DATABASE_URL` do `docker-compose.yml` — usa o valor do último `up`. Resolvido com `docker compose up -d backend` que recria o container.

Downtime backend total: **~3 min** (3 ciclos de up -d). Db e frontend intocados.

## Validações pós-rotação

- `GET /health` → 200.
- `POST /auth/login` com senha errada → 401 limpo (sem 500).
- `create_access_token` + `decode_access_token_full` em container: round-trip OK com chave nova, `jti` presente.
- `encrypt_secret` + `decrypt_secret` round-trip OK; `_vault_old()` ausente.

## Entrega dos novos segredos

Cifrado em:
- `/home/finadmin/backups/helpdesk/post-rotation-20260521-113459/new_secrets.env.enc`
- `/home/finadmin/backups/helpdesk/post-rotation-20260521-113459/env.post-rotation.enc`

Passphrase entregue ao Gilberg em chat. Esperado salvar no 1Password e shred local.

## Efeito visível ao usuário

- **Todos os JWT emitidos antes desta janela foram invalidados** — usuários ativos precisaram fazer novo login. Senhas (bcrypt no DB) intactas.
- Tokens revogados via `/auth/logout` (tabela `revoked_tokens`) que foram emitidos com a chave anterior ficaram órfãos — não causam mal, só ocupam espaço até `expires_at`. Não há necessidade de limpar.

## Pendente

- Rotação de `ZAPI_TOKEN` em janela coordenada com painel Z-API.
- Após 7 dias estáveis, flip de `SECURITY_*` audit → enforce.
