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
cd /home/finadmin/winthor-helpdesk
# editar .env, trocar a flag pra off ou audit
nano .env
docker compose restart backend
# validar
curl -s http://127.0.0.1:8010/api/v1/health | jq .
```

## Rollback completo (rebuild da imagem antes da fase)

VPS **não é git repo** — código é sincronizado via rsync a partir da máquina do dev.
Para reverter, fazer rsync do estado anterior e rebuildar:

```bash
# na maquina do dev
git checkout <SHA_ANTES_DA_FASE>
rsync -av --delete --exclude='.env' --exclude='media/' --exclude='backups/' \
  ./ finanpersona-vps:/home/finadmin/winthor-helpdesk/
# no VPS
ssh finanpersona-vps "cd /home/finadmin/winthor-helpdesk && docker compose build backend frontend && docker compose up -d"
```

## Snapshots (criados na Fase 0)

Localização real no VPS: `/home/finadmin/backups/helpdesk/pre-security-batch-1/`

- `db.sql.gz` — pg_dump do Postgres (user=helpdesk)
- `.env.plain` — copia do .env (chmod 600). Cifrar com age e shred do .plain
- `docker-compose.yml`, `Dockerfile.backend`, `Dockerfile.frontend` — snapshot da config
- `media.tar.gz` — tarball do volume `winthor-helpdesk_media_data`
- `phase-0-snapshot.txt` — estado de `docker compose ps`, imagens e volumes

## Restore de DB (último recurso)

```bash
ssh finanpersona-vps
cd /home/finadmin/winthor-helpdesk
docker compose stop backend
gunzip -c /home/finadmin/backups/helpdesk/pre-security-batch-1/db.sql.gz | \
  docker compose exec -T db psql -U helpdesk helpdesk
docker compose start backend
```

## Restore do volume de mídia

```bash
ssh finanpersona-vps
docker run --rm -v winthor-helpdesk_media_data:/data \
  -v /home/finadmin/backups/helpdesk/pre-security-batch-1:/backup alpine \
  sh -c "cd /data && rm -rf ./* && tar xzf /backup/media.tar.gz"
```
