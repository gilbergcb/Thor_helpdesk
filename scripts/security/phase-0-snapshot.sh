#!/usr/bin/env bash
# Phase 0 — snapshot pré-batch-1 de segurança.
# RODAR NO VPS antes da Fase 1. Idempotente.
set -euo pipefail

BACKUP_DIR="/opt/helpdesk/backups/pre-security-batch-1"
COMPOSE_DIR="/opt/helpdesk"

mkdir -p "$BACKUP_DIR"
cd "$COMPOSE_DIR"

echo "[1/4] Dump do banco..."
docker compose exec -T db pg_dump -U postgres helpdesk | gzip -9 > "$BACKUP_DIR/db.sql.gz"
echo "  -> $BACKUP_DIR/db.sql.gz ($(du -h "$BACKUP_DIR/db.sql.gz" | cut -f1))"

echo "[2/4] Cópia do .env (cifrar com age depois)..."
cp .env "$BACKUP_DIR/.env.plain"
chmod 600 "$BACKUP_DIR/.env.plain"
echo "  -> $BACKUP_DIR/.env.plain  (LEMBRE: 'age -r <pubkey> -o .env.age .env.plain && shred -u .env.plain')"

echo "[3/4] Anotando estado git e Docker..."
{
  echo "# Snapshot Phase 0 — $(date -Iseconds)"
  echo "## Git"
  git -C "$COMPOSE_DIR" log -1 --oneline
  git -C "$COMPOSE_DIR" status --short
  echo "## Docker"
  docker compose ps
  echo "## Images"
  docker compose images
} > "$BACKUP_DIR/phase-0-snapshot.txt"
echo "  -> $BACKUP_DIR/phase-0-snapshot.txt"

echo "[4/4] Hash do storage de mídia..."
find /opt/helpdesk/media -type f -printf '%P\n' 2>/dev/null | sort | \
  xargs -I{} sha256sum "/opt/helpdesk/media/{}" 2>/dev/null > "$BACKUP_DIR/media-hashes.txt" || true
echo "  -> $BACKUP_DIR/media-hashes.txt ($(wc -l < "$BACKUP_DIR/media-hashes.txt") arquivos)"

echo
echo "OK. Snapshot completo em $BACKUP_DIR"
echo "Próximo passo: rodar smoke tests (tests/smoke/SECURITY_SMOKE.md) e marcar baseline."
