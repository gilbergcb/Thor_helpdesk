# SECURITY REVIEW — THOR HelpDesk

**Data:** 2026-05-20
**Escopo:** Backend FastAPI + Frontend React/Vite + Integração Z-API + Docker
**Branch:** feature/contexto-mensagens-whatsapp
**Modo:** Read-only (nenhum arquivo de código foi alterado)

---

## Sumário Executivo

Foram identificados **23 achados**, sendo **3 Critical**, **6 High**, **8 Medium**, **4 Low** e **2 Info**.

**Achados mais graves (resumo):**

1. **CRITICAL** — Endpoints `GET /api/v1/media/{message_id}` e `/media/pending/{message_id}` **não exigem autenticação** e usam IDs sequenciais — IDOR completo, qualquer pessoa na rede pode enumerar e baixar mídias (imagens, áudios, PDFs) de todos os clientes.
2. **CRITICAL** — **Webhook `POST /api/v1/webhooks/zapi` não valida origem nem assinatura** — qualquer um pode forjar mensagens de WhatsApp, abrir tickets falsos, injetar conteúdo e disparar SSRF via `media_url` controlado pelo atacante.
3. **CRITICAL** — `download_to_storage()` faz HTTP GET seguindo redirects para qualquer URL fornecida no webhook → **SSRF** (acesso a metadata 169.254.169.254 da VPS, serviços internos como `db:5432`, etc.).
4. **HIGH** — Secrets de produção (senha Postgres, JWT_SECRET, token Z-API, VAULT_SECRET) presentes no `.env` local sem rotação aparente; arquivo não está no Git, mas é manuseado em workstation dev.
5. **HIGH** — Vários endpoints autenticados de tickets (`/tickets/{id}`, `/tickets/{id}/assign`, `/tickets/{id}/reply`, `/tickets/{id}/status`) **não verificam se o agente tem acesso ao ticket/cliente** — qualquer atendente vê e responde tickets de qualquer cliente (tenant isolation ausente).

---

## CRITICAL

### C1 — IDOR em endpoints de mídia (sem autenticação)
- **Localização:** `app/api/media.py:15-50`
- **Descrição:** As rotas `GET /api/v1/media/{message_id}` e `GET /api/v1/media/pending/{message_id}` não usam `Depends(get_current_agent)` nem nenhum tipo de auth. O ID é um inteiro sequencial.
- **Impacto:** Qualquer pessoa com acesso de rede ao backend pode enumerar `/media/1`, `/media/2`, … e baixar todas as mídias trocadas com clientes (imagens internas, documentos sensíveis, áudios) — vazamento massivo de dados de múltiplos tenants.
- **Recomendação:** Adicionar `Depends(get_current_agent)`, e validar autorização (atendente só pode acessar mídia de tickets atribuídos ao seu cliente / grupo). Considerar usar tokens assinados de curta duração na URL (signed URLs).

### C2 — Webhook Z-API sem validação de origem/assinatura
- **Localização:** `app/api/webhooks.py:13-18`
- **Descrição:** O endpoint aceita qualquer POST JSON sem verificar header secreto, assinatura HMAC, IP origin, mTLS ou similar.
- **Impacto:** Atacante externo pode:
  - Forjar mensagens "#chamado" abrindo tickets ilimitados (DoS, poluição de dados).
  - Forjar mensagens com `media_url` apontando para serviços internos da VPS → encadeia com C3 para SSRF.
  - Re-injetar (replay) eventos antigos.
  - Disparar `_send_open_confirmation` que envia mensagem real no grupo via Z-API (custo financeiro + spam).
- **Recomendação:** Implementar validação de webhook do Z-API (a Z-API suporta `Client-Token`/secret no header de webhook). Validar header constante em `secrets.compare_digest()`. Rejeitar payloads sem assinatura. Logar e rate-limitar.

### C3 — SSRF em `download_to_storage`
- **Localização:** `app/services/media_storage.py:41-67`
- **Descrição:** `httpx.stream("GET", url, follow_redirects=True)` é chamado com URL totalmente controlada pelo webhook (que por sua vez não é autenticado, ver C2). Sem allowlist de host, sem bloqueio de IPs privados/link-local, com 30s timeout e follow_redirects=True.
- **Impacto:** Acesso a serviços internos (`http://db:5432`, `http://169.254.169.254/latest/meta-data/` em clouds, `http://localhost:8000/api/v1/admin/...`), exfiltração via gravação em disco, side-channel de existência. Combinado com C1 o atacante pode até baixar o conteúdo via `/media/{id}`.
- **Recomendação:** Restringir host a domínio Z-API conhecido (`*.z-api.io`); resolver DNS e bloquear IPs em `ipaddress.ip_address().is_private/is_loopback/is_link_local/is_reserved`; desligar redirects ou validar a cada hop; limitar tamanho máximo (`Content-Length` + cap de bytes lidos).

---

## HIGH

### H1 — Tenant isolation ausente em endpoints de ticket
- **Localização:** `app/api/tickets.py:89-141`, `app/services/tickets.py` (`get_detail`, `reply`, `assign`, `change_status`)
- **Descrição:** Atendente autenticado pode `GET /tickets/{id}` de qualquer cliente/grupo, responder em nome do helpdesk para qualquer grupo WhatsApp, alterar status e assumir tickets de outros. Apenas o kanban filtra por `assigned_agent_id` para role atendente — os endpoints diretos por ID não.
- **Impacto:** Vazamento cross-tenant; atendente A consegue ler todos os tickets do atendente B / cliente B, e responder no grupo WhatsApp dele.
- **Recomendação:** No `TicketService`, validar `ticket.assigned_agent_id == agent.id or agent.role in (supervisor, admin)`. Para mídias e mensagens, mesmo check.

### H2 — Segredos de produção em `.env` local com valores reais
- **Localização:** `/Users/gilberg/ProjetosDev/HelpDesk/.env`
- **Descrição:** Arquivo contém POSTGRES_PASSWORD, JWT_SECRET_KEY, ZAPI_TOKEN, ZAPI_CLIENT_TOKEN, VAULT_SECRET_KEY — todos aparentando ser valores reais de produção em workstation dev. Não está commitado (verificado via `git log --all -- .env` retornou vazio) mas está em backups locais, `.venv` mac, Spotlight, etc.
- **Impacto:** Comprometimento da workstation = comprometimento total: acesso ao DB, forja de JWT, controle do WhatsApp do cliente, decifração de credenciais do vault.
- **Recomendação:** Rotacionar TODAS as chaves agora. Adotar gestor de segredos (1Password CLI, Doppler, AWS SM, sops+age). Manter no `.env` apenas valores de desenvolvimento. Adicionar `.env` ao `.gitignore` (já está) e instalar pre-commit hook (`gitleaks`).

### H3 — `VAULT_SECRET_KEY` cai em fallback para `JWT_SECRET_KEY`
- **Localização:** `app/core/security.py:27-31`
- **Descrição:** Se `vault_secret_key` não estiver setada, `_vault()` usa `jwt_secret_key`. Isso colapsa dois domínios de chave em um — vazar uma compromete a outra (credenciais do cliente decifradas + tokens JWT forjáveis).
- **Impacto:** Vazamento de uma única chave compromete dois sistemas críticos.
- **Recomendação:** Tornar `vault_secret_key` obrigatório (`assert settings.vault_secret_key`). Logar erro fatal no startup se ausente em produção.

### H4 — Bcrypt 3.2.2 (versão antiga) + senha mínima 6 caracteres
- **Localização:** `pyproject.toml` (bcrypt>=3.2.2,<4.0.0), `app/api/auth.py:38`
- **Descrição:** bcrypt está pinado em `<4.0.0` (a 4.x atual tem correções de robustez e desempenho). Política de senha aceita 6 caracteres, sem requisito de complexidade.
- **Impacto:** Senhas fracas viáveis (`123456`), brute-force factível dado que não há rate limit/lockout no login.
- **Recomendação:** Subir bcrypt para 4.x; exigir 12+ caracteres ou usar zxcvbn-py; adicionar rate-limit (`slowapi`) ou lockout temporário em `/auth/login`.

### H5 — CORS `allow_credentials=True` com `allow_methods=["*"]` e `allow_headers=["*"]`
- **Localização:** `app/main.py:11-17`
- **Descrição:** Apesar de `cors_origins` ser uma lista explícita, combinar `allow_credentials=True` com wildcard de methods/headers + `cors_origins` que em `.env` inclui `localhost:5173` e `localhost:8080` deixa origin escolha frágil. Se em prod algum operador adicionar `"*"` ou um host de teste, vira CSRF cross-site.
- **Impacto:** Risco de CSRF cross-origin se origin for relaxada.
- **Recomendação:** Listar methods e headers explicitamente; nunca permitir `*` quando `allow_credentials=True`; validar no startup que `cors_origins` não contém `*`.

### H6 — Endpoint `list_client_access_credentials` acessível a qualquer agente autenticado
- **Localização:** `app/api/admin.py:357-368`
- **Descrição:** Usa `Depends(get_current_agent)` em vez de `require_admin` — qualquer atendente consegue listar todos os títulos/URLs/usernames de credenciais sensíveis dos clientes. O segredo em si exige `reveal_token`, mas vazamento parcial já é grave.
- **Impacto:** Atendente comum vê inventário completo de quais sistemas/credenciais existem para cada cliente — útil para phishing direcionado.
- **Recomendação:** Aplicar `require_supervisor_or_admin` (ou `require_admin`) também no `list` e no `reveal`. Logar tentativas de reveal.

---

## MEDIUM

### M1 — JWT sem `iat`, `nbf`, `iss`, `aud`; sem invalidação no logout
- **Localização:** `app/core/security.py:46-60`
- **Descrição:** Payload tem só `sub` e `exp`. 8h de validade, sem refresh, sem revogação (logout só limpa localStorage).
- **Impacto:** Token vazado = 8h de acesso, sem como revogar; replay simples.
- **Recomendação:** Adicionar `jti` e tabela de revoked tokens, ou usar tokens de curta duração + refresh. Validar `iss`/`aud`.

### M2 — Token JWT armazenado em `localStorage`
- **Localização:** `frontend/src/services/api.ts:20,51,56`
- **Descrição:** Token JWT salvo em `localStorage`. Qualquer XSS exfiltra o token.
- **Impacto:** Combinado com qualquer XSS futuro (mídia maliciosa renderizada, dependência comprometida) compromete a sessão.
- **Recomendação:** Migrar para cookie `HttpOnly; Secure; SameSite=Strict` com endpoint de auth que set-cookie e CSRF token. Adicionar CSP estrito no nginx.

### M3 — `next_protocol()` provável race condition (gera IDs sequenciais)
- **Localização:** `app/services/webhook.py:60`, `app/repositories/tickets.py` (next_protocol — não inspecionado, mas inferido)
- **Descrição:** Em alta concorrência (webhook + criação manual), pode gerar protocolos duplicados ou previsíveis. Protocolos previsíveis facilitam enumeration.
- **Impacto:** Conflitos e/ou enumeration de tickets por protocolo.
- **Recomendação:** Sequence Postgres dedicada (`CREATE SEQUENCE`) ou UUID curto + check unique.

### M4 — Falta rate limit / brute force protection no login
- **Localização:** `app/api/auth.py:15-24`
- **Descrição:** Sem rate-limit, sem lockout, sem captcha. Combinado com H4 facilita brute force.
- **Recomendação:** `slowapi` ou `fastapi-limiter` (Redis) com 5 tentativas/15min por IP + por email.

### M5 — Mensagens de erro detalhadas (IntegrityError vaza schema)
- **Localização:** `app/api/admin.py:47-56` (`_commit_or_conflict`)
- **Descrição:** `message = str(exc.orig)` é retornado ao cliente truncado em 240 chars — vaza nomes de constraints/colunas Postgres.
- **Impacto:** Information disclosure facilitando reconnaissance.
- **Recomendação:** Logar internamente, devolver mensagem genérica ao cliente.

### M6 — Health endpoint sem proteção em prod (info disclosure mínima)
- **Localização:** `app/main.py:22-24`
- **Descrição:** Não é grave, mas em conjunto com `/docs` (FastAPI auto-docs ativo por padrão em produção pois `app = FastAPI(...)` não desabilita) expõe swagger UI inteira em prod.
- **Impacto:** `/docs` e `/openapi.json` expõem todo o mapa de rotas, schemas, modelos de auth — recon trivial.
- **Recomendação:** No `main.py`, em produção: `FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)` quando `settings.environment == "production"`.

### M7 — Imagens Docker rodando como root
- **Localização:** `Dockerfile:1-21`, `frontend/Dockerfile:1-14`
- **Descrição:** Nenhum `USER` definido — uvicorn e nginx rodam como root no container. Volume `media_data` é gravado como root.
- **Impacto:** Container escape = root; quaisquer paths/permissões expostas via SSRF/path traversal viram root.
- **Recomendação:** Adicionar `RUN useradd -m -u 1000 app && chown -R app:app /app /app/media` e `USER app`. Nginx-alpine já tem usuário `nginx`.

### M8 — Postgres port 55432 exposto (mesmo que em 127.0.0.1)
- **Localização:** `docker-compose.yml:9-10`
- **Descrição:** `127.0.0.1:55432:5432` — bom que está em loopback. Mas com senha de produção real (`xDCH...`) e Docker for Mac historicamente permitindo bypass de bind via plain bridge, recomenda-se remover o port mapping em produção.
- **Recomendação:** Em prod, remover o `ports:` do serviço `db` (acessível via rede interna do compose). Manter em dev se necessário.

---

## LOW

### L1 — `datetime.utcnow()` deprecated
- **Localização:** `app/services/media_storage.py:45`
- **Descrição:** `datetime.utcnow()` é deprecated no Python 3.12+. Mistura naive/aware com o restante do código que usa `datetime.now(UTC)`.
- **Recomendação:** Usar `datetime.now(UTC)`.

### L2 — `python-jose` 3.5.0 — projeto sem manutenção ativa
- **Localização:** `pyproject.toml`, uv.lock python-jose 3.5.0
- **Descrição:** `python-jose` teve CVEs históricos (algorithm confusion) e manutenção lenta. `decode_access_token` passa `algorithms=[HS256]` explicitamente (bom), mas a biblioteca não é recomendada.
- **Recomendação:** Migrar para `PyJWT` ou `authlib`.

### L3 — `caption` / `fileName` do webhook gravado sem sanitização
- **Localização:** `app/schemas/webhook.py:58`, `app/services/webhook.py:104`
- **Descrição:** Conteúdo livre vai para `Ticket.title` (180 chars), `description`, e depois renderizado no frontend. Embora React escape por padrão, qualquer integração futura via export PDF/email pode injetar.
- **Recomendação:** Sanitizar/normalizar (strip control chars, max length) e documentar contrato de trust.

### L4 — Sem CSP / security headers no nginx
- **Localização:** `frontend/nginx.conf`
- **Descrição:** Falta `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security`.
- **Recomendação:** Adicionar headers padrão de hardening no `server {}`.

---

## INFO

### I1 — `.env.example` documenta `ENVIRONMENT=production` como default
- **Localização:** `.env.example:2`
- **Descrição:** Misleading — default deveria ser `local` ou `development`. Pode fazer um operador rodar com flag de prod sem perceber.
- **Recomendação:** Trocar default para `development`.

### I2 — `bearer_scheme = HTTPBearer()` sem `auto_error=True` (default é True — ok)
- **Localização:** `app/api/deps.py:13`
- **Descrição:** Não é vulnerabilidade — apenas confirmar que `HTTPBearer` está rejeitando ausência de header (default ok). Documente para futuros mantenedores.

---

## Dependências — versões observadas

| Pacote | Versão | Status |
|---|---|---|
| fastapi | 0.136.1 | OK |
| sqlalchemy | 2.0.49 | OK |
| pydantic | 2.13.4 | OK |
| httpx | 0.28.1 | OK |
| python-jose | 3.5.0 | Manutenção lenta (L2) |
| passlib | 1.7.4 | OK (mas projeto idle) |
| bcrypt | 3.2.2 | Antiga (H4) |
| cryptography | 48.0.0 | OK |
| uvicorn | 0.47.0 | OK |
| react | 18.3.1 | OK |
| vite | 5.4.8 | OK |

Nenhuma versão com CVE crítico conhecido no momento desta review, ressalvas em H4 e L2.

---

## Checklist de remediação prioritária

1. **AGORA**: Rotacionar todas as chaves do `.env` (POSTGRES_PASSWORD, JWT_SECRET_KEY, VAULT_SECRET_KEY, ZAPI_TOKEN, ZAPI_CLIENT_TOKEN).
2. **AGORA**: Adicionar `Depends(get_current_agent)` em `app/api/media.py` + verificação de autorização por ticket/cliente.
3. **AGORA**: Validar header secret/HMAC no webhook Z-API.
4. **AGORA**: Restringir `download_to_storage` a hosts da Z-API e bloquear IPs privados.
5. **Próxima sprint**: Tenant isolation em todos os endpoints de `/tickets/{id}/*`.
6. **Próxima sprint**: Desabilitar `/docs` em produção; mover JWT para cookie HttpOnly; rate-limit no login; rodar containers como não-root; adicionar headers de segurança no nginx.
