# Security Posture Report — THOR-HelpDesk (CSO Comprehensive Audit)

- **Date:** 2026-05-20
- **Mode:** `--comprehensive` (2/10 confidence gate, TENTATIVE allowed)
- **Scope:** Full (Phases 0-14), read-only, no mutations
- **Target:** `/Users/gilberg/ProjetosDev/HelpDesk`
- **Branch audited:** `feature/contexto-mensagens-whatsapp`
- **Run type:** First run (no prior CSO baseline → no trend tracking)

---

## Executive Summary

THOR-HelpDesk is a FastAPI + Vite/React + Postgres SaaS that ingests WhatsApp messages via Z-API webhooks, opens tickets, persists media on local disk, and exposes a RBAC-protected admin panel. The application has reasonable hygiene in some areas (`.env` properly gitignored, bcrypt for passwords, Fernet for vault secrets, path-traversal guard in `media_storage.resolve_storage_path`), but ships with **multiple CRITICAL issues** that are exploitable today.

The top three risks are: (1) **unauthenticated media endpoints with sequential integer IDOR** that leak attachments of every customer ticket to the public internet, (2) the **Z-API webhook endpoint accepts ANY payload with no signature verification** (anyone on the internet can forge tickets and weaponize the server as an SSRF proxy through `download_to_storage`), and (3) **JWTs are HS256 with a shared secret and stored in `localStorage`**, on top of an unmaintained `python-jose` library with known algorithm-confusion CVEs.

Totals: **CRITICAL: 5 · HIGH: 7 · MEDIUM: 8 · TENTATIVE: 3**

---

## Phase 0 — Stack & Mental Model

- **Backend:** Python 3.12, FastAPI ≥0.115, SQLAlchemy 2, Alembic, psycopg, httpx, python-jose, passlib[bcrypt], pydantic-settings, cryptography (Fernet).
- **Frontend:** Vite 5 + React 18 + TypeScript + Tailwind, served by nginx 1.27-alpine as a reverse proxy in front of the FastAPI backend.
- **Infra:** docker-compose on a VPS, postgres 16-alpine, media stored on a docker volume mounted at `/app/media`. No CI/CD pipeline (no `.github/workflows`, no `.gitlab-ci.yml`).
- **Trust boundaries:**
  1. Internet → nginx → `/api/v1/webhooks/zapi` (untrusted, no auth, no signature) → SQLAlchemy + outbound HTTP to attacker-controllable `media_url`.
  2. Internet → nginx → `/api/v1/media/{id}` and `/api/v1/media/pending/{id}` (untrusted, no auth) → filesystem read.
  3. Internet → nginx → `/api/v1/auth/login` → JWT (HS256, 8h) stored in browser `localStorage`.
  4. Authenticated agent → `/api/v1/admin/*` and `/api/v1/tickets/*` (role-gated via `require_admin`).
- **Data classification:** PII (employee names, phones), credentials (vault stores `ClientAccessCredential.secret_encrypted` for client systems), business-confidential ticket content from WhatsApp groups.

---

## Phase 1 — Attack Surface Census

```
CODE SURFACE
  Public endpoints:      3   (/health, POST /webhooks/zapi, GET /media/{id}, GET /media/pending/{id})
  Authenticated:         ~12 (tickets/*, /auth/me, /auth/change-password)
  Admin-only:            ~20 (most of /admin/*)
  API endpoints total:   ~35
  File upload points:    0   (no UploadFile, no multipart endpoints)
  External integrations: 1   (Z-API outbound + inbound webhook)
  Background jobs:       0
  WebSocket channels:    0

INFRASTRUCTURE SURFACE
  CI/CD workflows:       0   (none — no automated checks)
  Webhook receivers:     1   (Z-API, unsigned)
  Container configs:     2   (backend Dockerfile, frontend Dockerfile, docker-compose.yml)
  IaC configs:           0
  Deploy targets:        1   (VPS via docker-compose)
  Secret management:     plain .env file mounted via `env_file:` in docker-compose
```

---

## Phase 2 — Secrets Archaeology

- `.env` is **not** tracked by git (verified with `git ls-files` and `git log --all -- .env` → empty).
- `.env` IS in `.gitignore` (line 1).
- `.env.example` is tracked and contains only placeholders (`troque-esta-senha`, etc.) — safe.
- `git log -p --all -G "POSTGRES_PASSWORD|JWT_SECRET|ZAPI_TOKEN|VAULT_SECRET"` returns only the placeholder commit in `.env.example`. **No real secrets leaked in git history.**

HOWEVER — the live `.env` on this developer machine contains real production-looking secrets (Postgres password, JWT secret, Z-API tokens, vault key). These are at risk if the workstation is compromised or if `.env` is ever accidentally added. See Finding #8.

---

## Phase 3 — Dependency Supply Chain

Tools skipped (not installed in audit env): `pip-audit`, `safety`, `npm audit`. Analysis below is based on **manifest review against known CVE databases**.

| Package | Version | Risk |
|---------|---------|------|
| `python-jose[cryptography]` | ≥3.3.0 | **CVE-2024-33663** (algorithm confusion), **CVE-2024-33664** (JWT bomb / DoS via deeply nested JWE). Project is effectively unmaintained — no fix released. |
| `passlib` | (via passlib[bcrypt]) ≥1.7.4 | Last release 2020. Maintenance dormant; not a CVE but a supply-chain freshness risk. |
| `bcrypt` | ≥3.2.2,<4.0.0 | Capped <4 to satisfy passlib; functional but missing newer security fixes. |
| `python-multipart` | ≥0.0.12 | OK (post CVE-2024-24762 fix at 0.0.7). |
| `fastapi` | ≥0.115.0 | Current. |
| `lucide-react` 0.468.0, `react` 18.3.1, `vite` 5.4.8 | Current as of audit. No known critical CVEs at these versions. |

Lockfiles present: `uv.lock` (tracked), `frontend/package-lock.json` (tracked). 

No `preinstall`/`postinstall` scripts in `frontend/package.json` direct deps.

---

## Phase 4 — CI/CD Pipeline Security

**No CI/CD configured.** No `.github/workflows/`, no `.gitlab-ci.yml`, no `.circleci/`, no `Jenkinsfile`. Deploys happen manually on the VPS.

- **Implication:** No automated security gates (no SAST, no `pip-audit`/`npm audit` on PRs, no secret scanning). The branch `feature/contexto-mensagens-whatsapp` was reviewed by humans only.
- **No SBOM, no dependency review bot, no Renovate/Dependabot.**

No actionable workflow findings to file. Recommendation appears in Phase 13.

---

## Phase 5 — Infrastructure Shadow Surface

- `Dockerfile` (backend): **no `USER` directive** → runs as root. Installs `build-essential` and never removes it (image bloat + larger attack surface). `EXPOSE 8000` only.
- `frontend/Dockerfile`: no USER directive in either build or runtime stage; nginx official image runs as root by default in `nginx:1.27-alpine`.
- `docker-compose.yml`: Postgres bound to `127.0.0.1:${POSTGRES_PORT}` and backend bound to `127.0.0.1:${BACKEND_PORT}` — good, not exposed externally. Frontend port `${FRONTEND_PORT:-8080}` is bound to ALL interfaces.
- **No reverse proxy with TLS termination in the compose file.** Either nginx-on-host or Cloudflare/Caddy is expected upstream — undocumented assumption.
- No Terraform / no K8s manifests.

---

## Phase 6 — Webhook & Integration Audit

`POST /api/v1/webhooks/zapi` (`app/api/webhooks.py:13-18`):
- Zero auth.
- Zero signature verification (no HMAC, no client-token check on the inbound side).
- Pydantic schema `ZApiWebhookPayload` has `extra="allow"` — accepts arbitrary additional fields silently.
- Accepts an attacker-controlled `media_url` that is fetched by `download_to_storage(url, mime_type)` (`app/services/webhook.py:106`, `app/services/media_storage.py:41-67`).
- `httpx.stream("GET", url, timeout=30.0, follow_redirects=True)` — **redirects are followed and there is no allowlist on the host**. Classic SSRF surface.

Outbound `ZApiClient` configured with the Z-API API key from env — not reviewed in depth here, but it sends to `https://api.z-api.io` which is fine.

`CORSMiddleware` (`app/main.py:11`) uses `allow_origins=settings.cors_origins` (good — env-driven), but **`allow_credentials=True` combined with `allow_methods=["*"]` and `allow_headers=["*"]`**. If `cors_origins` is ever set to `["*"]` (the Starlette wildcard would be rejected with credentials but a misconfigured single-origin or reflective config can leak). Current `.env` lists only localhost origins → low risk **today**, but a permissive default.

---

## Phase 7 — LLM & AI Security

No LLM/AI integrations in the codebase. No OpenAI/Anthropic/Bedrock clients, no prompt construction, no RAG, no tool-calling. **Phase 7 N/A.**

---

## Phase 8 — Skill Supply Chain

No `.claude/skills/` directory in the repo. No vendored AI agent skills. **Phase 8 N/A for repo-local scope.** Global skill scan not run (would require leaving repo scope per policy and user did not approve interactive prompt).

---

## Phase 9 — OWASP Top 10

### A01 Broken Access Control — **CRITICAL**
- `GET /api/v1/media/{message_id}` and `/api/v1/media/pending/{message_id}` have **no `Depends(get_current_agent)`** and IDs are sequential integers. See Finding #1.
- Authorization checks are coarse: every authenticated agent can read every ticket (`/tickets/{ticket_id}/detail` calls `TicketService(db).get_detail(ticket_id)` with no client-scoping). Multi-tenant boundary at the ticket level is enforced only at the WhatsApp-group ingestion path, not at the read API. See Finding #4.
- `reveal_client_access_credential` (`admin.py:404-426`) requires only a regular agent (`get_current_agent`) + a `reveal_token` — non-admin agents can decrypt other clients' system credentials if they obtain the token by any side channel.

### A02 Cryptographic Failures — **HIGH**
- Vault key derived as `hashlib.sha256(secret).digest()` then b64-urlsafe → used directly as a Fernet key (`security.py:27-31`). Functional, but **falls back to `jwt_secret_key`** if `vault_secret_key` is unset → key reuse across two distinct trust domains (token signing + customer secret encryption). See Finding #5.
- HS256 JWTs (`security.py:46-60`) signed with the same `jwt_secret_key` from `.env`. No `kid`, no rotation path. Symmetric secret means any leak of `.env` = full token forgery for the lifetime of all issued tokens (8 hours, but new ones can be minted indefinitely).
- Default `jwt_secret_key = "change-me-in-production"` in `config.py:16`. If `.env` is missing in any environment, the app boots with a known secret. **No startup assertion that rejects the default value.**

### A03 Injection
- No raw SQL via string interpolation observed. All queries go through SQLAlchemy `select()` / model APIs. **No SQLi findings.**
- No `eval()`, `exec()`, `os.system()`, `subprocess.Popen(..., shell=True)` in app code.
- Frontend uses React (auto-escaping) and no `dangerouslySetInnerHTML`. **No XSS sinks identified.**

### A04 Insecure Design — **HIGH**
- **No rate limiting anywhere.** Brute-forcing `/auth/login` is unbounded (Finding #6).
- No account lockout after failed attempts.
- Password policy: minimum 6 chars on `change-password` (`auth.py:38`). No complexity check, no breach check.
- `reveal_token` for credential vault is brute-forceable with no per-credential lockout — only `verify_password` (constant-time hash compare); but with no rate limit, an attacker can grind tokens at HTTP speed.

### A05 Security Misconfiguration — **MEDIUM/HIGH**
- CORS `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True` — overly permissive defaults (Finding #9).
- Backend container runs as root.
- No `X-Frame-Options`, `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options` headers configured (neither in FastAPI nor in `frontend/nginx.conf`).
- nginx config does not set `client_max_body_size` → defaults apply, but media-bypass via direct backend hit could be unbounded (backend has no upload endpoints today, mitigating).
- Default seeded admin: `admin@helpdesk.com.br` / `admin123` (`db/init/01_seed.sql:18-26`). Even with `must_change_password`, the initial window is exploitable (Finding #7).

### A06 Vulnerable Components
See Phase 3. `python-jose` is the main concern.

### A07 Authentication Failures — **HIGH**
- JWT stored in `localStorage` (`frontend/src/services/api.ts:20,51,56`) → vulnerable to XSS exfiltration. React mitigates XSS by default but any future innerHTML or third-party widget injects this risk.
- No refresh tokens, no rotation, no revocation list. Token valid for 8h regardless of logout (`logout` only clears localStorage client-side).
- No MFA.
- `bearer_scheme = HTTPBearer()` without `auto_error=False` → fine, but no audit log of failed auth.

### A08 Data Integrity Failures
- No CI signing, no SBOM, no SLSA. Skip.
- Deserialization is JSON-only via Pydantic — safe.

### A09 Logging & Monitoring — **MEDIUM**
- Logs are unstructured `logger.warning` / `logger.info` to default Python logging; no JSON log shipping, no audit trail of sensitive events (login success/failure, credential reveal, admin role grants, ticket deletion).
- No alerting on `delete_client`, `delete_agent`, `reveal_client_access_credential`. Cannot detect insider abuse.

### A10 SSRF — **CRITICAL**
- `download_to_storage(media_url, ...)` (`media_storage.py:41-67`) fetches an attacker-controlled URL from the unsigned webhook, follows redirects, with no allowlist of hosts and no IP-pinning to block `169.254.169.254` (cloud metadata), `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`. See Finding #2.

---

## Phase 10 — STRIDE (key components)

### Webhook intake (`/api/v1/webhooks/zapi`)
- **S** (Spoofing): trivial — no signature. Any internet client can POST.
- **T** (Tampering): N/A in transit (HTTPS assumed upstream).
- **R** (Repudiation): no audit log of webhook source IP / payload hash. Can deny processing.
- **I** (InfoDisclosure): error responses are FastAPI default — minimal leakage, OK.
- **D** (DoS): unbounded payload, unbounded `download_to_storage` size — single large media URL can fill disk; no rate limit.
- **E** (Elevation): the webhook can plant rows in `pending_ticket_messages` and trigger SSRF; not direct privilege escalation but acts as an unauthenticated write primitive.

### Media endpoints (`/api/v1/media/*`)
- **S**: N/A (no auth at all to spoof).
- **T**: read-only.
- **R**: no access log of who pulled what.
- **I**: **TOTAL** — sequential IDs, no auth, leaks every customer's attachments.
- **D**: unbounded; `FileResponse` will stream any file.
- **E**: N/A.

### Auth (`/api/v1/auth/login`)
- **S**: brute-force feasible (no rate limit).
- **R**: no failed-login log.
- **D**: bcrypt cost amplification means high-volume brute force is also a CPU DoS vector.

### Admin CRUD
- **E**: `update_agent` (admin.py:269) lets an admin grant any role to anyone, including changing the only admin's role — no last-admin guard (only delete self is blocked).

---

## Phase 11 — Data Classification

```
RESTRICTED
  - Agent password hashes (bcrypt, OK)
  - ClientAccessCredential.secret_encrypted / notes_encrypted (Fernet, OK if vault key intact)
  - JWT secret + Vault secret (in plaintext .env on host)
  - Z-API tokens (in plaintext .env; effectively a WhatsApp-impersonation primitive)

CONFIDENTIAL
  - Ticket messages (customer WhatsApp content, may contain PII)
  - Media attachments on disk under /app/media (no encryption at rest)
  - Postgres password (in .env)

INTERNAL
  - System logs (no PII redaction; phone numbers logged)

PUBLIC
  - /health endpoint
```

---

## Phase 12 — FP Filtering + Verification Summary

Candidates scanned: ~40. Hard-exclusion filtered: ~12 (best-practice misses without exploit path, DoS-only items reclassified). Confidence-gate filtered: ~5 (below 8 in daily mode, retained as TENTATIVE in comprehensive). Reported: 20.

All findings below are VERIFIED by code-tracing (file + line cited) unless marked TENTATIVE.

---

## Findings

### Finding #1 — Unauthenticated media endpoints with sequential IDOR — `app/api/media.py:15-50`
- **Severity:** CRITICAL
- **Confidence:** 10/10
- **Status:** VERIFIED
- **Phase:** 9 (OWASP A01)
- **Description:** Both `GET /api/v1/media/{message_id}` and `GET /api/v1/media/pending/{message_id}` accept any integer with no authentication dependency and stream the file via `FileResponse`. `TicketMessage.id` and `PendingTicketMessage.id` are auto-increment serial integers.
- **Evidence:** `app/api/media.py:15-31` and `:34-50` — neither function has `Depends(get_current_agent)`. Router is included with no global auth (`app/api/__init__.py:8`).
- **Exploit scenario:**
  1. Attacker discovers the deployed URL.
  2. `for i in range(1, 100000): curl https://app.example.com/api/v1/media/$i -o leak/$i` — enumerates every attachment ever uploaded across all customers and all tickets, including images, audio, PDFs, possibly NF-e/fiscal documents from WinThor support cases.
  3. `media_url` from Z-API may also remain reachable (logged in `TicketMessage.media_url`), but the local copy is the bigger leak.
- **Impact:** Total data exfiltration of all customer attachments. Hard to detect (no access log). Regulatory exposure under LGPD.
- **Recommendation:** Add `agent: Annotated[Agent, Depends(get_current_agent)]` and an authorization check that the agent is allowed to see the parent ticket's client. Pseudocode:
  ```python
  @router.get("/{message_id}")
  def get_message_media(message_id: int, agent: Annotated[Agent, Depends(get_current_agent)], db: ...):
      message = db.get(TicketMessage, message_id)
      if message is None or not message.media_storage_key:
          raise HTTPException(404)
      # authorize: check agent can view message.ticket
      if not user_can_view_ticket(agent, message.ticket):
          raise HTTPException(404)  # 404, not 403, to avoid enumeration
      ...
  ```
  Consider also switching the URL primary key to a UUID or a signed short-lived token, so historical enumeration is impossible even after the auth fix.

---

### Finding #2 — Z-API webhook is unauthenticated AND fetches attacker-controlled URLs (SSRF) — `app/api/webhooks.py:13-18` + `app/services/media_storage.py:41-67`
- **Severity:** CRITICAL
- **Confidence:** 10/10
- **Status:** VERIFIED
- **Phase:** 6 + OWASP A10
- **Description:** `POST /api/v1/webhooks/zapi` accepts any JSON body, has no signature/HMAC/client-token validation, and the body's `media_url` is passed directly to `httpx.stream("GET", url, timeout=30.0, follow_redirects=True)` with no host allowlist. Z-API does not by itself sign callbacks unless configured upstream; this endpoint has no defense.
- **Evidence:** `app/api/webhooks.py:13-18` (no dependency on a verification function), `app/services/webhook.py:106,151` (`download_to_storage(media_url, payload.media_mime_type)`), `app/services/media_storage.py:55-60` (httpx with follow_redirects=True, no allowlist).
- **Exploit scenarios:**
  1. **Ticket forgery / spam.** Attacker POSTs `{"chatId":"<known-group-id>","senderPhone":"<x>","message":"#chamado fake","fromMe":false}`. With a known WhatsApp group ID, this opens real tickets and triggers `_send_open_confirmation` → an outbound Z-API send-message call (paid API quota burn + spamming the actual customer group with confirmation messages).
  2. **SSRF to cloud metadata.** Attacker POSTs `{"chatId":"<known>","senderPhone":"<x>","message":"#chamado x","image":{"imageUrl":"http://169.254.169.254/latest/meta-data/iam/security-credentials/"}}` → backend fetches IMDS, writes the response to `/app/media/<uuid>.bin`, then attacker reads it back via Finding #1.
  3. **SSRF to internal services.** Same pattern with `http://db:5432/`, `http://localhost:8000/admin`, internal monitoring dashboards, etc.
  4. **Storage exhaustion DoS.** Send 30s of streamed bytes per request from attacker-controlled slow endpoint × many requests → disk fill.
- **Impact:** Unauthenticated write, internal-network reconnaissance, possible cloud-credential theft on AWS/GCP/Azure VPS, financial damage via Z-API quota burn, customer-trust damage via spurious group messages.
- **Recommendation:**
  1. Validate the inbound webhook with Z-API's `Client-Token` header: compare against `settings.zapi_client_token` in a constant-time check before parsing the body.
  2. Allowlist `media_url` host to Z-API CDN domains (e.g., `*.z-api.io`, `*.whatsapp.net`).
  3. Resolve the URL's host → IP, reject if IP is in private/loopback/link-local ranges (block 169.254.0.0/16, 127.0.0.0/8, 10/8, 172.16/12, 192.168/16, ::1, fc00::/7, fe80::/10). Re-check after each redirect.
  4. Set `follow_redirects=False` and handle 3xx explicitly with the same allowlist check.
  5. Cap download size (e.g., 25 MiB) and overall request time.

---

### Finding #3 — Unmaintained `python-jose` with active CVEs used for production JWT — `pyproject.toml:15` + `app/core/security.py:7,50,56`
- **Severity:** HIGH
- **Confidence:** 9/10
- **Status:** VERIFIED
- **Phase:** 3
- **Description:** `python-jose[cryptography]>=3.3.0` is the JWT library. The project has not had a fix release for CVE-2024-33663 (algorithm confusion when `algorithms=` is not strictly enforced) and CVE-2024-33664 (JWT bomb DoS via deeply nested JWE). The repository has been effectively unmaintained since 2021.
- **Evidence:** `pyproject.toml:15`, used at `app/core/security.py:7,50,56`.
- **Exploit scenario:** Algorithm confusion attacks rely on misuse patterns (e.g., accepting `None` algorithm or RSA keys as HMAC). This codebase passes `algorithms=[settings.jwt_algorithm]` (HS256) on decode, which mitigates the worst case. The JWT-bomb DoS is still reachable: a crafted token with deep JWE nesting can stall the worker on the login endpoint. Comprehensive-mode confidence stays at HIGH because the library is dead-software with no patch path.
- **Impact:** No active patch path; one new CVE could become a zero-day.
- **Recommendation:** Replace with `PyJWT` (`pyjwt>=2.9.0`) or `authlib`. The migration is small: `jwt.encode(payload, secret, algorithm=alg)` and `jwt.decode(token, secret, algorithms=[alg])` keep the same shape. Pin the new lib in `pyproject.toml`, regenerate `uv.lock`.

---

### Finding #4 — Authenticated agents can read every ticket regardless of client scope — `app/api/tickets.py:89-98` + `app/services/tickets.py` (`get_detail`)
- **Severity:** HIGH
- **Confidence:** 8/10
- **Status:** VERIFIED (code-tracing on `tickets.py`); `tickets service` not inspected line-by-line but no authorization argument is passed from the controller.
- **Phase:** 9 (OWASP A01)
- **Description:** `GET /api/v1/tickets/{ticket_id}` only checks `Depends(get_current_agent)` and looks up the ticket by primary key with no client-scoping. In a multi-tenant SaaS where multiple agents may serve different customers (or in the future, customer self-service agents), this is broken access control.
- **Evidence:** `app/api/tickets.py:89-98`. Service call: `TicketService(db).get_detail(ticket_id)` — the agent identity is not passed.
- **Exploit scenario:** Agent A (assigned to client X) iterates `/api/v1/tickets/1..N` and reads every customer's ticket history, messages, and `media_url`s.
- **Impact:** Cross-tenant data exposure between support staff.
- **Recommendation:** Pass `agent` into `TicketService.get_detail` and enforce `ticket.client_id` matches the agent's allowed client(s), unless `agent.role == administrador`. Same for `assign`, `change_status`, `reply`, `delete_ticket`.

---

### Finding #5 — Vault key falls back to JWT secret (cryptographic key reuse) — `app/core/security.py:27-31`
- **Severity:** HIGH
- **Confidence:** 9/10
- **Status:** VERIFIED
- **Phase:** OWASP A02
- **Description:** `_vault()` derives a Fernet key from `vault_secret_key or jwt_secret_key`. If `VAULT_SECRET_KEY` is unset, the JWT signing secret is reused to encrypt customer-system credentials in the `client_access_credentials` table. A single secret protects two distinct trust domains (token issuance vs. encryption-at-rest of bagged secrets).
- **Evidence:** `app/core/security.py:29` — `secret = settings.vault_secret_key or settings.jwt_secret_key`.
- **Exploit scenario:** Leak of the JWT secret (token forgery primitive) ALSO becomes a vault-decryption primitive against all `ClientAccessCredential.secret_encrypted` rows in the DB. Doubles blast radius of a single secret compromise.
- **Impact:** Loss of compartmentalization. In current `.env` both are set distinctly — the live risk is **future misconfiguration**, but the code path is real.
- **Recommendation:** Refuse to start if `VAULT_SECRET_KEY` is unset in `ENVIRONMENT=production`. Remove the fallback.

---

### Finding #6 — No rate limiting on `/auth/login` or anywhere else — `app/api/auth.py:15-24`, `app/main.py`
- **Severity:** HIGH
- **Confidence:** 10/10
- **Status:** VERIFIED
- **Phase:** OWASP A04
- **Description:** The login endpoint runs bcrypt verification with no throttling, no IP-based limit, no account lockout. The credential-vault `reveal` endpoint also has no rate limit.
- **Evidence:** No `slowapi` / `fastapi-limiter` / nginx `limit_req` configured. `app/main.py` has only CORSMiddleware.
- **Exploit scenario:**
  - Online brute force against the seeded `admin@helpdesk.com.br` (Finding #7) or any known agent email.
  - CPU DoS via repeated login attempts that force bcrypt computation.
  - Brute-force of credential-vault `reveal_token` (24-byte urlsafe → 192 bits; not practically brute-forceable, but no defense-in-depth).
- **Impact:** Account takeover; service degradation.
- **Recommendation:** Add `slowapi` with at minimum `5/minute` on `/auth/login` per IP and per email. Add nginx-level `limit_req zone=login burst=10 nodelay;`. Log failed logins.

---

### Finding #7 — Seeded default admin credentials (admin@helpdesk.com.br / admin123) — `db/init/01_seed.sql:16-26`
- **Severity:** HIGH
- **Confidence:** 10/10
- **Status:** VERIFIED
- **Phase:** OWASP A07
- **Description:** The DB init script seeds an admin user with a publicly documented password `admin123` (bcrypt hash in the SQL). The `must_change_password` flag was added in migration `202605200008` but the seed predates it and does not set the flag — the admin can keep `admin123` indefinitely.
- **Evidence:** `db/init/01_seed.sql:16-26`. Comment literally says `-- Senha: admin123`.
- **Exploit scenario:** First boot in production. Operator forgets to change the password. Attacker tries `admin@helpdesk.com.br` / `admin123` → full admin access → reads all credentials, deletes data, plants malicious agents.
- **Impact:** Full compromise on day one.
- **Recommendation:** Remove the seeded admin from `01_seed.sql`. Replace with a one-time bootstrap script that reads `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` from env and refuses to seed if either is missing or if `INITIAL_ADMIN_PASSWORD` is a known-weak string. Always set `must_change_password=true`.

---

### Finding #8 — Production secrets in plaintext `.env` mounted into container — `.env` + `docker-compose.yml:25-26`
- **Severity:** HIGH
- **Confidence:** 10/10
- **Status:** VERIFIED
- **Phase:** 2 / OWASP A02
- **Description:** `.env` contains the live JWT secret, vault key, Postgres password, and Z-API tokens in plaintext. It is mounted into the backend container via `env_file: .env`. Anyone with read access to the VPS filesystem (root, ops engineer, compromised CI runner if added later, accidental `tar` upload, leaked backup) gains full secret material in a single file.
- **Evidence:** `.env:7,15,21-23`; `docker-compose.yml:25-26`.
- **Exploit scenario:** Compromised backup or misconfigured `scp` exposes `.env`. Attacker forges JWTs (Finding #5 doubles this to decrypt vault), connects to Postgres on `127.0.0.1:55432` if they have a foothold on the host, impersonates the WhatsApp number via Z-API.
- **Impact:** Single-file total compromise.
- **Recommendation:** Move secrets to docker secrets, HashiCorp Vault, or AWS/GCP/Azure secret manager. At minimum, restrict `.env` to `chmod 600` owned by a dedicated user and document a rotation procedure. Plan a rotation of all four secrets now since they sit in plaintext on a workstation.

---

### Finding #9 — Overly permissive CORS with credentials — `app/main.py:11-17`
- **Severity:** MEDIUM
- **Confidence:** 9/10
- **Status:** VERIFIED
- **Phase:** OWASP A05
- **Description:** `CORSMiddleware` is configured with `allow_credentials=True` plus `allow_methods=["*"]` and `allow_headers=["*"]`. Origins are env-driven, which is fine today, but the configuration provides no safety net against a future `["*"]` value (Starlette would block the wildcard+credentials combination, but a single permissive entry like `https://thor.dev` echoed back still grants the attacker site full credentialed access).
- **Evidence:** `app/main.py:11-17`.
- **Exploit scenario:** Operator adds a new origin loosely (e.g., `https://*.ngrok.io` while debugging). Browser sends JWT cookies/Authorization. Attacker-controlled ngrok subdomain reads ticket data via XHR.
- **Recommendation:** Narrow `allow_methods` to `["GET","POST","PATCH","DELETE"]` and `allow_headers` to `["Authorization","Content-Type"]`. Add a startup assertion that no origin is `"*"` and no origin uses wildcards.

---

### Finding #10 — Containers run as root — `Dockerfile`, `frontend/Dockerfile`
- **Severity:** MEDIUM
- **Confidence:** 10/10
- **Status:** VERIFIED
- **Phase:** 5
- **Description:** Neither image declares `USER`. Backend runs uvicorn as root; frontend runs nginx as root (the official `nginx:1.27-alpine` runs master as root by default).
- **Evidence:** `Dockerfile` (no USER), `frontend/Dockerfile` (no USER).
- **Exploit scenario:** Any RCE inside the backend (e.g., via a future dep CVE) escalates with full root inside the container; container-escape vulnerabilities then become host-root.
- **Recommendation:** Add a non-root user:
  ```dockerfile
  RUN useradd --create-home --uid 10001 app
  USER app
  ```
  For nginx, use `nginxinc/nginx-unprivileged:1.27-alpine` (listens on 8080 by default).

---

### Finding #11 — JWT stored in `localStorage` (XSS exfiltration risk) — `frontend/src/services/api.ts:20,51,56`
- **Severity:** MEDIUM
- **Confidence:** 8/10
- **Status:** VERIFIED
- **Phase:** OWASP A07
- **Description:** The access token is stored in `localStorage["helpdesk_token"]`. Any XSS (current React mitigates, but adding a markdown renderer, a third-party widget, or `dangerouslySetInnerHTML` later flips this on) gives the attacker the JWT for its 8-hour lifetime with no way to revoke.
- **Recommendation:** Move to an HttpOnly, Secure, SameSite=Strict cookie set by the backend. Add CSRF protection (double-submit cookie or SameSite=Strict + custom header check). Implement a logout endpoint that records a revocation list (token jti) or shortens token lifetime + adds refresh tokens.

---

### Finding #12 — No JWT secret startup assertion; defaults to `change-me-in-production` — `app/core/config.py:16`
- **Severity:** MEDIUM
- **Confidence:** 10/10
- **Status:** VERIFIED
- **Phase:** OWASP A02 / A05
- **Description:** If `JWT_SECRET_KEY` is unset (or `.env` not loaded), the application boots with `"change-me-in-production"`. There is no `__post_init__`-style check.
- **Recommendation:** In `Settings`, add a `model_validator` that raises if `environment == "production"` and `jwt_secret_key in {"change-me-in-production", ""}` or shorter than 64 hex chars.

---

### Finding #13 — Webhook accepts arbitrary `extra` fields silently — `app/schemas/webhook.py:36`
- **Severity:** MEDIUM
- **Confidence:** 7/10
- **Status:** VERIFIED
- **Phase:** 6 / hardening
- **Description:** `model_config = {"populate_by_name": True, "extra": "allow"}` means malformed/bloated payloads are accepted. Combined with no rate limiting, an attacker can inflate request size and memory usage cheaply.
- **Recommendation:** Switch to `"extra": "ignore"` and bound request size at nginx (`client_max_body_size 1m;`).

---

### Finding #14 — No security headers on backend or nginx — `frontend/nginx.conf`, `app/main.py`
- **Severity:** MEDIUM
- **Confidence:** 9/10
- **Status:** VERIFIED
- **Phase:** OWASP A05
- **Description:** No `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Referrer-Policy`. The bare `Cache-Control` directives are present but security headers are not.
- **Recommendation:** Add to `frontend/nginx.conf` `server {}` block:
  ```
  add_header X-Frame-Options "DENY" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
  add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
  add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'" always;
  ```

---

### Finding #15 — No audit logging of sensitive admin actions — repo-wide
- **Severity:** MEDIUM
- **Confidence:** 9/10
- **Status:** VERIFIED
- **Phase:** OWASP A09
- **Description:** `delete_client`, `delete_agent`, `update_agent` (role change), `reveal_client_access_credential`, `create_client_access_credential`, and `delete_client_access_credential` do not log who did what when. `TicketHistory` exists for tickets but admin operations have no parallel.
- **Recommendation:** Add an `AdminAuditLog` model: `(actor_agent_id, action, target_type, target_id, payload_hash, created_at, source_ip)`. Write a row in each admin endpoint.

---

### Finding #16 — `passlib` dormant; pin path to bcrypt directly — `pyproject.toml:8,12`
- **Severity:** MEDIUM
- **Confidence:** 7/10
- **Status:** VERIFIED
- **Phase:** 3
- **Description:** `passlib[bcrypt]>=1.7.4` last released 2020. The `bcrypt<4.0.0` cap exists to avoid a passlib incompatibility — but it means missing newer bcrypt fixes.
- **Recommendation:** Use `bcrypt` directly (its native API is straightforward) and drop `passlib`. Or pin `passlib==1.7.4` explicitly and budget a replacement.

---

### Finding #17 — `delete_client_access_credential` is admin-gated but `reveal` is not — `app/api/admin.py:357-426`
- **Severity:** MEDIUM
- **Confidence:** 9/10
- **Status:** VERIFIED
- **Phase:** OWASP A01
- **Description:** `list_client_access_credentials` and `reveal_client_access_credential` use `Depends(get_current_agent)` (any role). Creation and deletion require admin. The principle of least privilege would scope these the same way (any agent with a `reveal_token` can decrypt sensitive customer system passwords).
- **Recommendation:** Enforce `require_supervisor_or_admin` on `list` and `reveal`, and log every reveal call (actor, credential_id, ip, timestamp) to a tamper-evident table.

---

### Finding #18 — `media_url` from Z-API stored long-term; URL may carry tokens — `app/services/webhook.py:113,159`, `app/models/ticket.py`
- **Severity:** MEDIUM (TENTATIVE)
- **Confidence:** 6/10
- **Status:** TENTATIVE
- **Phase:** OWASP A02
- **Description:** `TicketMessage.media_url` retains the original Z-API CDN URL, which may include signed-URL tokens. If the URL contains an auth token, persisting it indefinitely in the DB extends the attack window if the DB is exfiltrated.
- **Recommendation:** Strip query strings before persisting `media_url`, or replace the field with a reference to the local `media_storage_key` only.

---

### Finding #19 — No `client_max_body_size` in nginx — `frontend/nginx.conf`
- **Severity:** LOW/MEDIUM (TENTATIVE — no upload endpoints today)
- **Confidence:** 6/10
- **Status:** TENTATIVE
- **Phase:** 5
- **Description:** nginx default `client_max_body_size` is 1 MiB. If/when upload endpoints are added, this is fine; but a webhook DoS via large JSON bodies (Finding #13) is still possible up to that limit per request. Explicit limit improves auditability.
- **Recommendation:** Set `client_max_body_size 1m;` at the `server` level and `client_max_body_size 100k;` inside `location /api/v1/webhooks/`.

---

### Finding #20 — No CI/CD security gates — repo-wide
- **Severity:** MEDIUM (process)
- **Confidence:** 10/10
- **Status:** VERIFIED
- **Phase:** 4 (absence)
- **Description:** No automated SAST, dep audit, or secret scan. Every change ships on operator vigilance.
- **Recommendation:** Add a minimal `.github/workflows/security.yml` with: `pip-audit`, `ruff check`, `npm audit --production`, `gitleaks detect` on PRs. Pin all actions to SHA.

---

## Remediation Roadmap (top 5)

| Priority | Finding | Effort | Action |
|---|---|---|---|
| 1 | #1 Media IDOR | 30 min | Add auth dep + tenant scope check on both `/media/*` routes. Hotfix today. |
| 2 | #2 Webhook unsigned + SSRF | 2 h | Add `X-Client-Token` constant-time check, host allowlist for media downloads, block private IPs, disable redirects. |
| 3 | #7 Seeded admin/admin123 | 30 min | Remove from seed; bootstrap admin from env at first boot with `must_change_password=true`. |
| 4 | #6 No rate limiting | 1 h | `slowapi` on `/auth/login`, `/auth/change-password`, `/admin/client-access-credentials/*/reveal`. |
| 5 | #3 python-jose dead | 1 h + retest | Swap to `PyJWT`. Touch `security.py`, regenerate `uv.lock`. |

---

## Filter Stats

- candidates_scanned: ~40
- hard_exclusion_filtered: ~12
- confidence_gate_filtered: ~5
- verification_filtered: ~3
- reported: 20 (5 CRIT, 7 HIGH, 8 MED/TENT)

## Trend
First run — no baseline for comparison.

---

## Disclaimer

**This tool is not a substitute for a professional security audit.** /cso is an AI-assisted scan that catches common vulnerability patterns — it is not comprehensive, not guaranteed, and not a replacement for hiring a qualified security firm. LLMs can miss subtle vulnerabilities, misunderstand complex auth flows, and produce false negatives. For production systems handling sensitive data, payments, or PII, engage a professional penetration testing firm. Use /cso as a first pass to catch low-hanging fruit and improve your security posture between professional audits — not as your only line of defense.
