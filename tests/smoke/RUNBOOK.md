# Runbook — Rollback Convergência de Segurança

Cada fase tem 2 caminhos de rollback: **feature flag** (rápido, sem redeploy) e **revert de commit** (definitivo).

## Convenção de flags

Todas as mudanças comportamentais entram atrás de uma env `SECURITY_*` com default **seguro mas compatível**:

| Flag | Default Fase | Significado |
|---|---|---|
| `SECURITY_MEDIA_AUTH` | `audit` → `enforce` | `off`/`audit`/`enforce` para guard de IDOR em `/media/*` |
| `SECURITY_WEBHOOK_HMAC` | `audit` → `enforce` | valida Client-Token Z-API |
| `SECURITY_SSRF_ALLOWLIST` | `audit` → `enforce` | restringe hosts em `download_to_storage` |
| `SECURITY_TENANT_ISOLATION` | `audit` → `enforce` | filtra tickets por `agent → client` |
| `SECURITY_VAULT_DUAL_KEY` | `on` | aceita cifra antiga (JWT) e nova (VAULT_SECRET_KEY) |
| `SECURITY_RATELIMIT_LOGIN` | `on` | rate-limit `/auth/login` |

## Rollback rápido (zero downtime)

```bash
ssh finanpersona-vps
cd /opt/helpdesk
# editar .env, trocar a flag pra off ou audit
sudo nano .env
docker compose restart api
# validar
curl -s https://helpdesk.thor.<dominio>/api/v1/health | jq .
```

## Rollback completo (git revert)

```bash
cd /opt/helpdesk
git log --oneline -10
git revert <SHA_DA_FASE>
docker compose build api && docker compose up -d api
```

## Snapshots (criados na Fase 0)

- DB: `/opt/helpdesk/backups/pre-security-batch-1/db.sql.gz`
- .env: `/opt/helpdesk/backups/pre-security-batch-1/env.age` (cifrado com age, chave do Gilberg)
- Compose: commit SHA no git anotado em `phase-0-snapshot.txt`

## Restore de DB (último recurso)

```bash
docker compose stop api
gunzip -c /opt/helpdesk/backups/pre-security-batch-1/db.sql.gz | \
  docker compose exec -T db psql -U postgres helpdesk
docker compose start api
```
