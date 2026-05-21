# Plano — Portal público de ticket: anexos + paste de clipboard

**Data:** 2026-05-21
**Autor:** Claude + Gilberg
**Status:** PROPOSTO — aguarda aprovação para começar implementação
**Branch sugerida:** `feature/public-portal-uploads`
**Pré-requisito merge:** PR #2 (security convergence) mergeado em `main`

---

## 1. Contexto

Hoje o portal público `/t/<token>` (renderizado por `frontend/src/pages/PublicTicketPage.tsx`) só permite ao cliente **ler** o ticket e **enviar texto** via `POST /public/tickets/{token}/messages`. O cliente final (que recebeu o link no WhatsApp) precisa anexar evidências — prints de erro, logs de NF-e, planilhas — sem ter que voltar pro WhatsApp.

Objetivo: permitir que o cliente, autenticado **só pelo token público**, suba arquivos junto com a mensagem. Em particular:
- Botão de "anexar" que abre o file picker do SO (imagens + texto + PDF).
- Cole de área de transferência (`Ctrl+V` num textarea ativo cola screenshot/imagem).
- Preview dos anexos antes de enviar.
- Múltiplos anexos por mensagem.

Tudo isso convivendo com a Fase 1 da convergência de segurança (F-01 media auth, F-03 SSRF, F-14 non-root, F-16 CSP).

---

## 2. Decisões de design

### 2.1 Endpoint único multipart

`POST /public/tickets/{token}/messages` muda de `application/json` para `multipart/form-data`. Campos:

| Campo | Tipo | Notas |
|---|---|---|
| `message` | text | opcional se houver anexo; cap 4000 chars |
| `files` | file[] | até 4 por request; opcional se houver texto |

Resposta: continua sendo `PublicTicketRead` (lista atualizada de mensagens, agora com anexos).

**Por que não endpoint separado de upload?** Atomicidade. Um POST = uma mensagem coerente no chat. Sem orfãos.

### 2.2 Modelo de dados — nova tabela

Hoje `TicketMessage` tem só `media_storage_key`/`media_type`/`media_mime_type` (uma mídia por linha — herança do webhook Z-API). Para suportar N anexos por mensagem sem refator gigante, cria-se:

```sql
ticket_message_attachments (
  id              BIGINT PK,
  ticket_message_id INT FK -> ticket_messages.id ON DELETE CASCADE,
  storage_key     VARCHAR(255) NOT NULL,
  mime_type       VARCHAR(120) NOT NULL,
  byte_size       INT NOT NULL,
  original_filename VARCHAR(255),  -- sanitizado; nunca usado em filesystem
  source          VARCHAR(16) NOT NULL,  -- 'public_portal' | 'webhook_zapi' | 'agent_reply'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
CREATE INDEX ix_attachments_message ON ticket_message_attachments(ticket_message_id);
```

**Migração de dados existente:** os `media_storage_key` legados em `TicketMessage` continuam funcionando. Frontend tenta `attachments[]` primeiro, fallback no campo antigo. Backfill em batch separado (opcional, fase 3).

### 2.3 Limites e validação

| Limite | Valor | Onde aplicar |
|---|---|---|
| Tamanho por arquivo | **15 MB** | backend (size cap) + frontend (UX) |
| Arquivos por mensagem | **3** | backend (count) + frontend |
| MIME whitelist | `image/png`, `image/jpeg`, `image/webp`, `image/gif`, `application/pdf`, `text/plain`, `text/csv`, `application/json` | backend (libmagic se disponível, fallback header+ext) |
| MIME blacklist explícita | `image/svg+xml`, `text/html`, `application/x-*`, `*/zip`, scripts | backend |
| Total por token por hora | **50 MB** | backend (somatório em janela móvel) |
| nginx `client_max_body_size` em `/api/v1/public/` | **50 MB** (3 × 15 MB + folga de cabeçalho/multipart boundary) | `frontend/nginx.conf` |
| EXIF strip | **desabilitado** | — (decisão Gilberg: geolocalização não é preocupação) |
| Eco para WhatsApp via Z-API | **desabilitado nesta fase** | fica para fase 2 |

### 2.4 Storage

Reusa `app/services/media_storage.py`. Novo método `save_uploaded_file(stream, suggested_ext)`:
- Salva em `/app/media/YYYY/MM/<uuid>.<ext>` (mesmo layout do webhook).
- Container roda uid 10001 (F-14) — volume já chowned.
- Retorna `storage_key` relativo.

### 2.5 Servir mídia em link público (conflito com F-01)

Quando flipar `SECURITY_MEDIA_AUTH=enforce`, `/media/<id>` exige Bearer JWT. Mas o viewer do portal público **não tem JWT** — só o token público.

**Solução:** nova rota `GET /public/tickets/{token}/attachments/{attachment_id}` que:
1. Valida o token público (mesma lógica do `get_public_ticket`).
2. Verifica que `attachment_id` pertence a `ticket_id` do link.
3. Serve o arquivo via `FileResponse` (mesma `resolve_storage_path` do `media.py`).
4. Sem dependência do F-01 guard.

Frontend usa essa URL nos `<img src>` do portal. Painel admin continua usando `/media/<id>`.

### 2.6 Eco para o WhatsApp

**Fase 1 (escopo deste plano):** **NÃO** ecoa pro WhatsApp. Anexos sobem só pro portal/painel. Atendente vê no `TicketDrawer`. Cliente final só vê no portal.

**Fase 2 (futuro):** método `ZApiClient.send_group_image()` / `send_group_document()` espelhando o upload no grupo. Adiciona dependência do Z-API e teste de envio.

Decisão: separar para reduzir surface deste PR e manter UX consistente — se Z-API estiver fora do ar, upload do portal não pode falhar.

---

## 3. Mudanças por camada

### 3.1 Backend

**Migrations**
- `alembic/versions/2026052X_ticket_message_attachments.py` — cria tabela + index.

**Modelos**
- `app/models/ticket.py` — adicionar `TicketMessageAttachment` com relação `attachments` em `TicketMessage`.
- `app/models/__init__.py` — exportar.

**Storage**
- `app/services/media_storage.py` — novo `save_uploaded_file(file_stream, content_type, suggested_filename)`. Detecção MIME por libmagic (`python-magic`) se disponível, fallback `mimetypes.guess_extension`.
- `pyproject.toml` — adicionar `python-magic>=0.4.27` (libmagic via apt no Dockerfile: `apt install -y libmagic1`).

**Schemas**
- `app/schemas/public.py`:
  - `PublicTicketAttachmentRead` (id, mime_type, byte_size, original_filename, url) — `url` calculado: `/api/v1/public/tickets/<token>/attachments/<id>`.
  - `PublicTicketMessageRead.attachments: list[PublicTicketAttachmentRead]`.

**Endpoints**
- `app/api/public.py`:
  - `POST /public/tickets/{token}/messages` migrado de JSON → multipart (`UploadFile` + `Form("message")`). Validação MIME/size/count, persiste TicketMessage com N attachments numa transação. Audit log estruturado.
  - `GET /public/tickets/{token}/attachments/{attachment_id}` — serve arquivo, valida pertencimento.
- `app/core/ratelimit.py` — novo limit `3/min` específico para upload (mais agressivo que o `10/min` do POST text-only).
- `app/api/public.py` — quota check: somatório de bytes uploaded por token na última hora ≤ 50 MB.

**Auditoria**
- Logger `security.public_uploads` registra: `actor_ip`, `token_fingerprint`, `ticket_id`, `count`, `total_bytes`, `mimes_detected`.
- F-18 `record_admin_action` NÃO se aplica aqui (não é ação admin); usar log estruturado.

### 3.2 Frontend

**Tipos** (`frontend/src/types/api.ts`)
- `PublicTicketAttachment { id, mime_type, byte_size, original_filename, url }`.
- `PublicTicketMessage.attachments: PublicTicketAttachment[]`.

**API client** (`frontend/src/services/api.ts`)
- `sendPublicTicketMessage(token, message, files)` muda assinatura. Constrói `FormData`. Não setar `Content-Type` (browser põe boundary).

**Página** (`frontend/src/pages/PublicTicketPage.tsx`)

Composer fica:

```
┌─────────────────────────────────────────────────┐
│ [textarea — paste habilitado]                    │
│                                                  │
├─────────────────────────────────────────────────┤
│ 📎 Anexar arquivos   (Cole prints com Ctrl+V)    │
├─────────────────────────────────────────────────┤
│ Previews:                                        │
│ [thumb.png ×]  [error.log ×]  [+2 mais ×]       │
├─────────────────────────────────────────────────┤
│              [Enviar mensagem  ➤]                │
└─────────────────────────────────────────────────┘
```

Implementação:
- `useState<File[]>` para anexos pendentes.
- Hidden `<input type=file accept="..." multiple ref>` + botão visível dispara `inputRef.current?.click()`.
- `onPaste` handler no `textarea`:
  ```ts
  for (const item of e.clipboardData.items) {
    if (item.kind === 'file') {
      const f = item.getAsFile();
      if (f) appendAttachment(f);
    }
  }
  ```
- Drag-and-drop opcional na própria área (`onDragOver` + `onDrop`).
- Validação cliente: size ≤ 5MB, mime na whitelist, count ≤ 4.
- Preview: imagens via `URL.createObjectURL(file)`; texto via ícone genérico + nome.
- Lembrar de `URL.revokeObjectURL` no unmount.

**Renderização de mensagens com anexos**
- Mensagem inbound do cliente (direction=`inbound`, source=`public_portal`) mostra grid de thumbs abaixo do texto. Click abre lightbox simples.

**Estilo** (`frontend/src/styles/index.css`)
- Bloco `.thor-public-composer-attachments` com grid responsivo.

### 3.3 Infra

**`frontend/nginx.conf`**
- Nova location `/api/v1/public/tickets/`:
  ```nginx
  location /api/v1/public/tickets/ {
    client_max_body_size 25m;
    proxy_pass http://backend:8000/api/v1/public/tickets/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    include /etc/nginx/snippets/security-headers.conf;
  }
  ```
  (vem antes da `location /api/` genérica que tem 1m).

**`Dockerfile` (backend)**
- `apt install libmagic1` adicionado (necessário pro `python-magic`).

**Migration deploy**
- Standard: `alembic upgrade head` no CMD já roda.

---

## 4. Fases de entrega

Cada fase é um commit verificável; permite parar/reverter.

### Fase A — backend MVP (~3h)
1. Migration + modelos.
2. Endpoint POST multipart.
3. Endpoint GET attachment.
4. Rate limit + size cap + MIME whitelist.
5. Testes manuais via `curl --form`.
6. Deploy VPS, smoke.

**Gate:** anexo via curl funciona, MIME rejeita SVG/HTML/zip, size cap funciona.

### Fase B — frontend composer (~2h)
1. `FormData` no API client.
2. Botão de anexo + file picker.
3. `onPaste` no textarea.
4. Preview grid + remoção.
5. Validação cliente.

**Gate:** consigo abrir o portal, colar um print do Cmd+Shift+4 do Mac, ver preview, enviar, ver no painel admin.

### Fase C — renderização anexos no chat (~1h)
1. Tipo `PublicTicketAttachment` + render de thumbs.
2. Lightbox/expansão.
3. Adaptar `TicketDrawer` do painel admin pra também mostrar `attachments[]`.

**Gate:** atendente abre ticket no painel, vê os anexos que o cliente subiu via portal.

### Fase D — hardening (~1h)
1. nginx body size em location específica.
2. libmagic via apt no Dockerfile.
3. Quota horária por token.
4. Audit logging estruturado.
5. CSP review (a CSP atual aceita `img-src 'self' data: blob:` → OK para upload via portal).

**Gate:** sobe 5 imagens de 4MB cada, 5ª retorna 413. Sobe `bash.sh` renomeado `bash.png` → backend detecta via libmagic e rejeita.

### Fase E — polimento (opcional, ~1h)
1. EXIF strip em imagens (`Pillow.Image.save` sem exif).
2. Thumbnails server-side (Pillow resize) servidos via novo endpoint.
3. Click → download forçado com `Content-Disposition: attachment`.

---

## 5. Checklist de segurança

- [ ] MIME validado via libmagic (não confiar em header).
- [ ] Extensão derivada do MIME detectado (não do filename do user).
- [ ] Filename original sanitizado (regex `[^\w.\- ]` → `_`, cap 100 chars), só pra display.
- [ ] SVG bloqueado (XSS).
- [ ] HTML bloqueado (XSS).
- [ ] Scripts/archives bloqueados (malware drop).
- [ ] Size cap server-side (não confiar no browser).
- [ ] Count cap por request.
- [ ] Quota horária por token.
- [ ] Rate limit dedicado mais agressivo (3/min).
- [ ] Audit log com IP, token fingerprint, mimes.
- [ ] Link público só serve attachment do próprio ticket (FK check).
- [ ] `Content-Disposition: attachment` para tipos não-renderizáveis (evita execução inline).
- [ ] CSP `img-src 'self'` cobre — ok.
- [ ] nginx `client_max_body_size` em location específica (não global em 25m).
- [ ] Quando F-01 flipar pra enforce: rota `/public/tickets/.../attachments/<id>` continua acessível.
- [ ] Soft-revoke: ticket fechado revoga token → tentativa de upload retorna 404.
- [ ] DOS: subir 100 requests com arquivo 4.9MB → rate limit 3/min trava no 4º. Quota trava em ~10 uploads/hora.

---

## 6. Não-objetivos (fora do escopo)

- Espelhar uploads pro WhatsApp via Z-API. (Fase 2)
- Editar/deletar anexo depois de enviado.
- Antivírus (ClamAV). (Fase 3 se demanda real surgir)
- Audio recording in-portal.
- Vídeo upload.
- Compressão server-side de imagens.

---

## 7. Riscos identificados

| Risco | Mitigação |
|---|---|
| nginx truncar upload silenciosamente | `client_max_body_size 25m` em location específica + 413 explícito |
| python-magic não instalado → MIME detection fraca | Fallback no header + extension match; fail-closed se ambos divergem |
| `/api/v1/media/<id>` deixar de funcionar quando F-01 flip enforce | nova rota pública dedicada `/public/tickets/<token>/attachments/<id>` |
| Cliente subir 4×5MB num grupo lento → timeout | nginx `client_body_timeout 60s`; tela de progresso no frontend |
| FormData não setar Content-Type → erro | Sempre `fetch(url, {body: formData})` sem `Content-Type` no headers — browser injeta com boundary |
| Race: ticket fecha entre validação e save | Re-check `link = get_valid_link(token)` antes do commit final |
| Atendente já trabalhando no painel não vê anexos novos | refresh polling existente ainda cobre; ou WebSocket fase 2 |

---

## 8. Estimativa total

- Fases A+B+C+D: **~7h de trabalho focado**.
- Migration aplica em ~50ms (tabela vazia).
- Deploy: 2 rebuilds (backend pelo Dockerfile mudar com libmagic; frontend pelo nginx.conf). Downtime esperado ~10s backend + ~5s frontend.
- Janela coordenada não necessária — sem rotação de segredo, sem migração destrutiva.

---

## 9. Decisões finais (aprovadas por Gilberg)

1. ✅ PDF entra.
2. ✅ Quota 50 MB/hora por token.
3. ✅ Tamanho máx por arquivo: **15 MB**.
4. ✅ EXIF strip: **NÃO** (geolocalização não é preocupação no contexto Thor).
5. ✅ Eco para WhatsApp: **NÃO** nesta fase.
6. ✅ **Max 3 arquivos por request** (ajustado por consistência matemática: 3 × 15 MB = 45 MB ≤ 50 MB/hora).

---

## 10. Próximo passo

Aprovar este plano (com eventuais ajustes nas decisões 1–5) e criar a branch `feature/public-portal-uploads` a partir de `main` (após PR #2 mergeado). Daí eu começo pela Fase A e te aviso a cada gate.
