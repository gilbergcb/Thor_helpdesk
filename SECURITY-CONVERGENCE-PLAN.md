# Plano de Convergência de Segurança — THOR HelpDesk

**Data:** 2026-05-20
**Base:** `SECURITY-REVIEW.md` (auditor manual, 23 achados) + `SECURITY-REVIEW-CSO.md` (CSO comprehensive, 20 achados)
**Objetivo:** Remediar os achados convergentes e divergentes **sem quebrar nada que está funcionando hoje em produção**.
**Princípio reitor:** *cada mudança entra com flag/compat shim, é validada em staging com testes de fumaça, e só então o caminho legado é removido.*

---

## 1. Sumário consolidado

| # | Achado | Manual | CSO | Severidade final | Risco de regressão |
|---|---|---|---|---|---|
| F-01 | IDOR em `/api/v1/media/*` | C1 | #1 | **CRITICAL** | Médio — frontend e webhook consomem essas URLs |
| F-02 | Webhook Z-API sem auth/HMAC | C2 | #2 | **CRITICAL** | Alto — quebra integração se token errado |
| F-03 | SSRF em `download_to_storage` | C3 | #2 | **CRITICAL** | Baixo — restringir hosts não muda fluxo legítimo |
| F-04 | Vault key fallback → JWT secret | H3 | #5 | **HIGH** | Médio — invalida vault se chave não migrada |
| F-05 | Tenant isolation ausente em `/tickets/*` | H1 | #4 | **HIGH** | Alto — pode bloquear atendentes hoje |
| F-06 | Seed `admin@helpdesk.com.br` / `admin123` | — | #7 | **HIGH** | Alto — deploy novo sem admin = lockout |
| F-07 | `python-jose` abandonado (CVE-2024-33663/33664) | L2 | #3 | **HIGH** | Médio — troca de lib + invalidação de tokens |
| F-08 | Segredos em `.env` plaintext | H2 | #8 | **HIGH** | Médio — rotação requer redeploy coordenado |
| F-09 | Sem rate-limit em `/auth/login` + bcrypt antigo | H4 | #6 | **HIGH** | Baixo |
| F-10 | `list/reveal_client_access_credentials` sem RBAC | H6 | #17 | **HIGH** | Médio — pode quebrar UI atual de supervisor |
| F-11 | CORS permissivo | H5 | #9 | **MEDIUM** | Baixo |
| F-12 | JWT sem `jti`/revogação, em `localStorage` | M1+M2 | #11 | **MEDIUM** | Alto — migrar p/ cookie quebra fluxo de login |
| F-13 | JWT secret default `change-me-in-production` | — | #12 | **MEDIUM** | Baixo |
| F-14 | Docker rodando como root | M7 | #10 | **MEDIUM** | Médio — volumes podem ter perm. errada |
| F-15 | `/docs` Swagger exposto em prod | M6 | (Phase 5) | **MEDIUM** | Baixo |
| F-16 | Sem security headers no nginx | L4 | #14 | **MEDIUM** | Baixo |
| F-17 | Webhook `extra="allow"` + sem `client_max_body_size` | — | #13+#19 | **MEDIUM** | Baixo |
| F-18 | Sem audit log de ações admin | — | #15 | **MEDIUM** | Nenhum |
| F-19 | `media_url` Z-API persistido com query/token | — | #18 | **MEDIUM** | Baixo |
| F-20 | Sem CI/CD com gates de segurança | — | #20 | **MEDIUM** | Nenhum |
| F-21 | IntegrityError vaza schema | M5 | — | **LOW** | Baixo |
| F-22 | `next_protocol()` race possível | M3 | — | **LOW** | Médio — mudança de geração de protocolo |
| F-23 | `datetime.utcnow()` deprecated | L1 | — | **LOW** | Nenhum |
| F-24 | Postgres port exposto em loopback | M8 | (Phase 5) | **LOW** | Baixo |
| F-25 | `caption`/`fileName` sem sanitização | L3 | — | **LOW** | Baixo |
| F-26 | `.env.example` default `production` | I1 | — | **INFO** | Nenhum |

**Convergência:** 14 achados aparecem nos dois relatórios — esses são os de **maior confiança** e devem entrar primeiro. Achados únicos do CSO (F-06, F-07, F-13, F-18, F-19, F-20) são reais e foram aceitos. Achados únicos do manual (F-22, F-23, F-24, F-25) ficam em fase posterior.

---

## 2. Estratégia anti-regressão

Antes de qualquer mudança:

1. **Branch dedicado:** `security/convergence-batch-1` a partir de `feature/contexto-mensagens-whatsapp`. Cada fase = 1 PR pequeno e revisável.
2. **Baseline de testes de fumaça** (registrar HOJE, antes de mexer):
   - Login admin + atendente.
   - Abertura de ticket via webhook Z-API real (msg `#chamado` em grupo de teste).
   - Recebimento de mídia (imagem) — verificar storage + render.
   - Resposta a ticket pelo frontend → mensagem chega no WhatsApp.
   - CRUD em Clientes/Grupos/Agentes pelo AdminPanel.
   - Mudança de status no kanban.
3. **Snapshot de DB e `.env`** em `/opt/helpdesk/backups/pre-security-batch-1/`.
4. **Feature flags** via env (`SECURITY_*`) para cada mudança comportamental — permite rollback sem redeploy de código.
5. **Janelas de deploy:** sempre fora do horário comercial (após 19h ou domingo). Rollback plan documentado em cada PR.
6. **Observabilidade:** adicionar logs estruturados em cada novo guard antes de ativá-lo em modo enforce — primeiro `audit-only`, depois `enforce`.

---

## 3. Fases de execução

Cada fase tem **gate de saída** (smoke tests verdes + 24h sem alerta) antes da próxima começar.

---

### FASE 0 — Preparação (D-1, ~2h, sem deploy)

**Não muda código de produção.**

- [ ] Criar branch `security/convergence-batch-1`.
- [ ] Snapshot de DB (`pg_dump`) e cópia do `.env` atual cifrada (age/gpg).
- [ ] Documentar os smoke tests acima em `tests/smoke/SECURITY_SMOKE.md`.
- [ ] Gerar **novos** valores para: `JWT_SECRET_KEY` (64 bytes), `VAULT_SECRET_KEY` (32 bytes para Fernet), `POSTGRES_PASSWORD`, e solicitar **novo** `ZAPI_TOKEN` + `ZAPI_CLIENT_TOKEN` no painel Z-API (mas ainda **não trocar** — só guardar).
- [ ] No painel Z-API, configurar/registrar o **Client-Token** que será enviado no header do webhook (necessário para F-02).
- [ ] Confirmar com o time qual janela de deploy.

**Gate:** smoke baseline registrado em texto, segredos novos gerados e guardados, equipe avisada.

---

### FASE 1 — Hotfixes Critical (D-day, janela noturna, ~2h)

Objetivo: fechar os 3 CRITICAL convergentes (F-01, F-02, F-03) **sem mexer em fluxo legítimo**.

#### 1.1 — F-01: IDOR em mídia (`app/api/media.py`)

- Adicionar `Depends(get_current_agent)` em ambos os endpoints.
- Verificar autorização: `message.ticket.assigned_agent_id == agent.id OR agent.role in (supervisor, administrador)`.
- Retornar **404** (não 403) para evitar enumeração.
- **Compat para frontend:** o frontend hoje já envia `Authorization: Bearer` em todas as chamadas (visto em `api.ts`); confirmar com Grep que `/media/` é chamado via `api.ts` e não via `<img src>` direto. Se for via `<img src>` (sem header), introduzir **signed URL de curta duração** como ponte:
  - Novo endpoint `POST /api/v1/media/{id}/signed-url` autenticado → devolve `?token=...&exp=...`.
  - Endpoint `GET /api/v1/media/{id}` aceita **token assinado OU JWT bearer** durante 7 dias (período de compat).
  - Depois de 7 dias, remover suporte a token sem JWT.

**Risco/rollback:** se mídia parar de carregar, reverter via flag `SECURITY_MEDIA_AUTH=off`. Manter o código antigo atrás do flag por uma semana.

#### 1.2 — F-02: Webhook Z-API sem validação (`app/api/webhooks.py`)

- Ler header `Client-Token` (Z-API envia esse header se configurado no painel).
- Comparar com `settings.zapi_inbound_token` via `secrets.compare_digest()`.
- **Modo gradual:**
  - Sprint 1: `SECURITY_WEBHOOK_AUTH=audit` → loga `WARNING` se token ausente/inválido mas **não rejeita**.
  - Sprint 1 + 48h: verificar logs, garantir 100% das requests legítimas chegando com token.
  - Sprint 1 + 72h: virar `SECURITY_WEBHOOK_AUTH=enforce` → 401 se inválido.
- Adicionar rate-limit por IP no endpoint (slowapi, `100/min`).

**Risco/rollback:** se Z-API parar de entregar (token mal configurado), reverter para `audit`. Modo audit-only é seguro porque não muda comportamento, só observa.

#### 1.3 — F-03: SSRF em `download_to_storage` (`app/services/media_storage.py`)

- Allowlist de hosts: `{"*.z-api.io", "*.whatsapp.net", "mmg.whatsapp.net", "media.whatsapp.net"}`.
- Resolver DNS antes do GET; rejeitar se IP cair em `ipaddress.ip_address(ip).is_private or .is_loopback or .is_link_local or .is_reserved`.
- `follow_redirects=False`; tratar 3xx manualmente repassando pelo guard.
- Cap de tamanho: parar leitura em 25 MiB (`max_bytes=25*1024*1024`).
- Timeout total: 15s (era 30s).

**Risco/rollback:** mídias de domínios não-listados deixam de baixar. Mitigar:
- Antes de ativar, rodar 24h em modo `audit` logando todos os hosts que aparecem em `media_url`.
- Atualizar allowlist com base nos logs.
- Só então ativar `enforce`.

**Gate Fase 1:** smoke tests passam, webhook continua recebendo (modo audit), mídias carregam, sem 5xx novo em 24h.

---

### FASE 2 — Hardening HIGH (D+3 a D+10, ~6h em 3 PRs)

#### 2.1 — F-06: Remover seed `admin123` (`db/init/01_seed.sql`)

- Remover INSERT do admin do seed.
- Adicionar script `scripts/bootstrap_admin.py` que lê `INITIAL_ADMIN_EMAIL` + `INITIAL_ADMIN_PASSWORD` do env e cria com `must_change_password=true`.
- No `docker-compose.yml`, rodar via `command:` do entrypoint só se não existir admin.
- **Compat:** em ambientes existentes, o admin já foi criado — script é no-op (`if Agent.query.filter_by(role=admin).count() > 0: skip`). **Não derruba** instalações vivas.

**Risco/rollback:** baixíssimo — código novo só roda em DB vazio.

#### 2.2 — F-04: Vault key obrigatória (`app/core/security.py`)

- Em `Settings`, `model_validator`: se `environment == "production"` e `vault_secret_key in (None, "", jwt_secret_key)` → raise.
- Em dev/staging, manter fallback com `WARNING`.
- **Migração de dados:** se em produção a vault estava usando o JWT secret, os ciphertexts existentes só decifram com a chave antiga. Plano:
  1. Adicionar suporte a **dupla chave**: `VAULT_SECRET_KEY_NEW` + `VAULT_SECRET_KEY_OLD`. Decifra tentando nova → cai pra antiga.
  2. Job `re_encrypt_all_credentials()` recria os ciphertexts com chave nova.
  3. Remover suporte à antiga após 30 dias.
- Se a vault NUNCA recebeu fallback (config tinha `VAULT_SECRET_KEY` setado), a migração é só `assert` no startup — zero risco.

**Risco/rollback:** segredos perdidos se chave antiga sumir. Backup obrigatório de `client_access_credentials` antes.

#### 2.3 — F-09: Rate-limit + bcrypt (`app/api/auth.py`, `pyproject.toml`)

- Adicionar `slowapi` (em memória ou Redis se já houver).
- Limites: `/auth/login` → `5/min` por IP + `10/hour` por email; `/auth/change-password` → `5/hour` por agent.
- Subir `bcrypt` para `>=4.2.0` e adicionar tag em `passlib` (que aceita 4.x desde 1.7.5; revalidar). Se passlib quebrar, migrar `app/core/security.py` para usar `bcrypt` puro (API simples: `bcrypt.hashpw`/`checkpw`).
- Política de senha: mínimo 12 chars no `change-password`. **Não invalida senhas existentes** — só aplica em troca futura.

**Risco/rollback:** se bcrypt+passlib quebrarem o login, rollback do pacote. Testar localmente com hashes do banco antes de fazer deploy.

#### 2.4 — F-10: RBAC em `client_access_credentials`

- `list` e `reveal` → `Depends(require_supervisor_or_admin)`.
- **Antes do enforce**, fazer Grep no frontend para descobrir quem chama esses endpoints. Se a UI hoje permite atendente ver a lista, precisa esconder (já há gating de role no `App.tsx`).
- Adicionar log estruturado de cada `reveal`: `{actor, credential_id, ip, ts}`.

**Risco/rollback:** se atendente realmente precisa ver lista hoje, criar `require_agent_with_grant` e habilitar feature flag por agente.

**Gate Fase 2:** smoke + login funcionando, sem 401 inesperado, atendentes seguem trabalhando.

---

### FASE 3 — Rotação de segredos + supply chain (D+10 a D+17, ~4h, requer janela)

#### 3.1 — F-08: Rotacionar TODOS os segredos

Janela noturna. Ordem:

1. Gerar novos valores (já feito na Fase 0).
2. Backup do DB.
3. `docker compose down`.
4. Substituir `.env` no host com novos valores. **Manter VAULT_SECRET_KEY_OLD setado** (Fase 2.2) para decifrar.
5. `docker compose up -d`.
6. Smoke: login funciona (JWT novo é assinado com chave nova — todos os JWT atuais ficam inválidos = todos deslogam, **avisar usuários**), abrir ticket via webhook (token Z-API novo já configurado no painel), responder ticket (saída Z-API com token novo), revelar credencial (vault decifra via OLD).
7. Rodar `re_encrypt_all_credentials()`.
8. Remover `VAULT_SECRET_KEY_OLD` após confirmar.

**Risco/rollback:** se algo falhar, voltar `.env` antigo. Por isso a chave antiga fica disponível.

#### 3.2 — F-07: Trocar `python-jose` por `PyJWT`

- `app/core/security.py`: `from jose import jwt` → `import jwt`. APIs são compatíveis (`jwt.encode(payload, key, algorithm=...)` / `jwt.decode(token, key, algorithms=[...])`).
- Atualizar `pyproject.toml` e `uv.lock`.
- Tokens emitidos pela versão antiga continuam válidos (mesmo segredo HS256, mesmo formato). **Nenhum logout forçado**.
- Cobertura de teste em `tests/test_security.py`: gerar token com python-jose, decodificar com PyJWT, e vice-versa, para garantir migração sem flag-day.

**Risco/rollback:** baixo — APIs equivalentes. Se quebrar, reverter o commit.

#### 3.3 — F-13: Startup assert do JWT secret

- `Settings.model_validator`: rejeita boot em prod se `jwt_secret_key in {"change-me-in-production", ""}` ou len < 32.
- Em dev, só `WARNING`.

**Gate Fase 3:** sistema continua funcional após rotação, nenhum agente trancado fora, vault decifra tudo.

---

### FASE 4 — Tenant isolation + hardening de infra (D+17 a D+30, ~8h)

#### 4.1 — F-05: Tenant isolation em `/tickets/*`

**O mais delicado.** Hoje atendente acessa qualquer ticket. Plano:

1. Auditar uso real: rodar 7 dias com log `audit-only` em `TicketService.get_detail/reply/assign/status` — registrar `{agent_id, agent_role, ticket_id, ticket_assigned_to, ticket_client_id}`.
2. Definir regra: atendente vê apenas tickets onde `assigned_agent_id == agent.id` **OU** `assigned_agent_id IS NULL` **E** `ticket.client_id in agent.allowed_clients` (se não houver `allowed_clients`, atendente vê só os atribuídos).
3. Supervisor e administrador veem tudo.
4. Adicionar campo `agent_client_access` (tabela N:N) **opcional** — se vazia para um atendente, fallback ao comportamento antigo (compat).
5. Ativar enforce após 7 dias de audit limpo.

**Risco/rollback:** alto — pode bloquear atendentes. Por isso 7 dias de observação + feature flag por endpoint.

#### 4.2 — F-14: Docker non-root

- Backend `Dockerfile`: `RUN useradd -m -u 10001 app && chown -R app:app /app` + `USER app`.
- Frontend: trocar `nginx:1.27-alpine` por `nginxinc/nginx-unprivileged:1.27-alpine` (porta 8080 internamente; ajustar `docker-compose.yml`).
- **Permissões do volume `media_data`:** rodar `chown -R 10001:10001` no diretório do volume no host **antes** do primeiro deploy. Sem isso, container novo não consegue escrever.

**Risco/rollback:** se permissões quebrarem, reverter Dockerfile.

#### 4.3 — F-15: Desabilitar `/docs` em produção

- `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` quando `settings.environment == "production"`.
- Manter em dev/staging.

#### 4.4 — F-16: Security headers no nginx

- Adicionar bloco do CSO (Finding #14) no `frontend/nginx.conf`.
- CSP: começar em `Report-Only` por 7 dias, coletar violations, depois enforce.

#### 4.5 — F-11: CORS estrito

- Substituir `allow_methods=["*"]` e `allow_headers=["*"]` por listas explícitas.
- Adicionar startup assert: nenhuma origem é `"*"`.

#### 4.6 — F-17: Webhook `extra="ignore"` + `client_max_body_size`

- Em `app/schemas/webhook.py`: `model_config["extra"] = "ignore"`.
- nginx: `client_max_body_size 100k;` em `location /api/v1/webhooks/`, `1m` no resto.

**Gate Fase 4:** smoke + 7 dias estáveis. Sem CSP violations bloqueantes.

---

### FASE 5 — Observabilidade e processo (D+30 a D+45)

#### 5.1 — F-18: Audit log de ações admin

- Tabela `admin_audit_log`: `(id, actor_agent_id, action, target_type, target_id, payload_hash, source_ip, created_at)`.
- Hook em: `delete_client`, `delete_agent`, `update_agent` (role change), `create/reveal/delete_client_access_credential`, `delete_ticket`.
- Exposição via endpoint admin `/admin/audit-log` paginado.

#### 5.2 — F-12 (parcial): JWT com `jti` + endpoint de logout

- Adicionar `jti` (uuid) ao payload do JWT.
- Tabela `revoked_tokens(jti, exp)`. Endpoint `POST /auth/logout` insere; middleware checa.
- **Não migrar para cookie HttpOnly ainda** — alto risco, fica para Fase 6.

#### 5.3 — F-20: CI/CD com gates

- `.github/workflows/security.yml`: `pip-audit`, `npm audit --omit=dev`, `gitleaks detect`, `ruff check`.
- Não falha PR no início (warn-only), vira blocker após 2 semanas.
- Adicionar Dependabot para `pip` e `npm`.

#### 5.4 — F-19: Strip de query string em `media_url`

- No `webhook.py`, persistir `media_url.split("?")[0]` em `TicketMessage.media_url`.
- Migração one-shot para limpar histórico (opcional).

**Gate Fase 5:** pipelines verdes, audit log gravando, logout invalidando token.

---

### FASE 6 — Mudanças invasivas (futuras, planejar à parte)

Não entram nesta convergência sem refactor coordenado:

- **F-12 (completo): JWT em cookie HttpOnly + CSRF** — muda fluxo de login do frontend, requer endpoint set-cookie, CSRF middleware, e ajuste de todas as chamadas de `api.ts`. Planejar em sprint dedicada.
- **F-22: `next_protocol()` com sequence Postgres** — requer migration + revisão de unicidade. Baixa prioridade.
- **Migrar de `passlib` para `bcrypt` puro (F-16 CSO)** — depende de F-09.

---

## 4. Matriz de risco × valor

```
Alto valor / Baixo risco  →  F-01, F-03, F-06, F-09, F-13, F-15, F-16, F-17, F-18, F-20
Alto valor / Médio risco  →  F-02 (modo audit-first), F-04 (dupla chave), F-07, F-10
Alto valor / Alto risco   →  F-05, F-08, F-12, F-14 (todos com plano detalhado acima)
Baixo valor / Baixo risco →  F-11, F-19, F-21, F-23, F-25, F-26 (incluir em PRs de oportunidade)
```

---

## 5. Cronograma sugerido

| Semana | Fase | Esforço dev | Janela deploy |
|---|---|---|---|
| 1 | Fase 0 + Fase 1 (CRIT) | ~4h | 1 noite |
| 2 | Fase 2 (HIGH não-rotação) | ~6h | 2 noites |
| 3 | Fase 3 (rotação + jose) | ~4h | 1 noite + aviso |
| 4-5 | Fase 4 (tenant + infra) | ~8h | 2 noites |
| 6-7 | Fase 5 (observabilidade) | ~6h | rolling |
| 8+ | Fase 6 (refactor JWT cookie) | sprint própria | — |

---

## 6. Checklist de "pronto para produção" (a cada PR)

- [ ] Branch criada a partir do main atualizado.
- [ ] Mudança coberta por teste unitário ou integração quando aplicável.
- [ ] Feature flag ou modo `audit` antes de `enforce`.
- [ ] Backup do `.env` e do banco antes do deploy.
- [ ] Rollback plan escrito no corpo do PR.
- [ ] Smoke tests do `tests/smoke/SECURITY_SMOKE.md` rodados em staging.
- [ ] Logs/observabilidade adicionados para detectar regressão.
- [ ] Janela de deploy fora do horário comercial.
- [ ] Aviso ao time se afetar sessões ativas (rotação de JWT).

---

## 7. Riscos residuais aceitos nesta convergência

- **F-12 (cookie HttpOnly):** mantido `localStorage` por mais 1-2 sprints; mitigado com `jti` + revogação (Fase 5).
- **F-22 (next_protocol):** mantido até primeiro conflito observado.
- **F-08 (gestor de segredos externo):** mantido `.env` no host com `chmod 600` até decisão sobre Doppler/Vault.

---

## 8. Aceite

| Item | Responsável | Data |
|---|---|---|
| Aprovação do plano | Gilberg | __/__/__ |
| Owner técnico Fase 1 | __ | __/__/__ |
| Owner técnico Fase 2-3 | __ | __/__/__ |
| Owner técnico Fase 4-5 | __ | __/__/__ |

---

*Plano construído a partir da convergência de SECURITY-REVIEW.md (auditoria manual) e SECURITY-REVIEW-CSO.md (gstack /cso comprehensive). Achados de confiança máxima (presentes nos dois relatórios) priorizados nas Fases 1-2.*
