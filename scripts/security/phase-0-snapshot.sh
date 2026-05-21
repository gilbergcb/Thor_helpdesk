#!/usr/bin/env bash
# Phase 0 — snapshot pré-batch-1 de segurança.
# RODAR NO VPS finanpersona-vps (user finadmin) antes da Fase 1. Idempotente.
set -euo pipefail

COMPOSE_DIR="${HELPDESK_DIR:-/home/finadmin/winthor-helpdesk}"
BACKUP_DIR="${BACKUP_DIR:-/home/finadmin/backups/helpdesk/pre-security-batch-1}"
PG_USER="${POSTGRES_USER:-helpdesk}"
PG_DB="${POSTGRES_DB:-helpdesk}"
MEDIA_VOLUME="winthor-helpdesk_media_data"

mkdir -p "$BACKUP_DIR"
cd "$COMPOSE_DIR"

echo "[1/5] Dump do banco (user=$PG_USER db=$PG_DB)..."
docker compose exec -T db pg_dump -U "$PG_USER" "$PG_DB" | gzip -9 > "$BACKUP_DIR/db.sql.gz"
echo "  -> $BACKUP_DIR/db.sql.gz ($(du -h "$BACKUP_DIR/db.sql.gz" | cut -f1))"

echo "[2/5] Cópia do .env (cifrar com age depois)..."
cp .env "$BACKUP_DIR/.env.plain"
chmod 600 "$BACKUP_DIR/.env.plain"
echo "  -> $BACKUP_DIR/.env.plain  (LEMBRE: 'age -r <pubkey> -o .env.age .env.plain && shred -u .env.plain')"

echo "[3/5] Snapshot do docker-compose.yml e Dockerfiles..."
cp docker-compose.yml "$BACKUP_DIR/docker-compose.yml"
cp Dockerfile "$BACKUP_DIR/Dockerfile.backend"
cp frontend/Dockerfile "$BACKUP_DIR/Dockerfile.frontend" 2>/dev/null || true

echo "[4/5] Anotando estado Docker..."
{
  echo "# Snapshot Phase 0 — $(date -Iseconds)"
  echo "## Path"; echo "$COMPOSE_DIR"
  echo "## Docker ps"
  docker compose ps
  echo "## Images"
  docker compose images
  echo "## Volumes"
  docker volume ls | grep -i helpdesk
} > "$BACKUP_DIR/phase-0-snapshot.txt"
echo "  -> $BACKUP_DIR/phase-0-snapshot.txt"

echo "[5/5] Dump tarball do volume de mídia (read-only mount)..."
docker run --rm -v "${MEDIA_VOLUME}:/data:ro" -v "$BACKUP_DIR:/backup" alpine \
  sh -c "cd /data && tar czf /backup/media.tar.gz . && sha256sum /backup/media.tar.gz" \
  > "$BACKUP_DIR/media-tarball.sha256" 2>&1 || echo "  (volume vazio ou erro — ok se nada cadastrado)"
ls -la "$BACKUP_DIR/media.tar.gz" 2>/dev/null && echo "  -> media.tar.gz pronto"

echo
echo "OK. Snapshot completo em $BACKUP_DIR"
echo "Próximo passo: rodar smoke tests (tests/smoke/SECURITY_SMOKE.md) e marcar baseline."
