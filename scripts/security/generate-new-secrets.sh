#!/usr/bin/env bash
# Phase 0 — gerar NOVOS segredos. NÃO TROCA NADA EM PRODUÇÃO.
# Saída: .env.new (na cwd). Guardar em local seguro (1Password / age).
set -euo pipefail

OUT="${1:-.env.new}"

if [[ -e "$OUT" ]]; then
  echo "ERRO: $OUT já existe. Apague ou escolha outro nome." >&2
  exit 1
fi

# JWT_SECRET_KEY — 64 bytes base64-urlsafe
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

# VAULT_SECRET_KEY — chave Fernet (32 bytes base64). cryptography precisa estar instalado.
VAULT_SECRET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# POSTGRES_PASSWORD — 32 bytes urlsafe (sem chars problemáticos pra connstring)
PG_PASS=$(python3 -c "import secrets,string; alpha=string.ascii_letters+string.digits; print(''.join(secrets.choice(alpha) for _ in range(40)))")

cat > "$OUT" <<EOF
# Gerado em $(date -Iseconds) — NÃO COMMITAR
# Guardar em 1Password / age. Usar somente na rotação coordenada (Fase 3).

JWT_SECRET_KEY=$JWT_SECRET
VAULT_SECRET_KEY=$VAULT_SECRET
POSTGRES_PASSWORD=$PG_PASS

# TODO manual:
# - ZAPI_TOKEN          (regenerar no painel Z-API antes do deploy da Fase 1)
# - ZAPI_CLIENT_TOKEN   (configurar no painel Z-API → Webhook → Client-Token)
# - SMTP_PASSWORD       (se houver — rotacionar manualmente)
EOF

chmod 600 "$OUT"

echo "OK. Segredos gravados em $OUT (chmod 600)."
echo "PRÓXIMO PASSO MANUAL:"
echo "  1. Mover para vault (1Password / age):  age -r <pubkey> -o ${OUT}.age $OUT && shred -u $OUT"
echo "  2. No painel Z-API: gerar novo token + configurar Client-Token p/ webhook."
echo "  3. NÃO atualizar produção ainda — só Fase 3 fará a troca coordenada."
