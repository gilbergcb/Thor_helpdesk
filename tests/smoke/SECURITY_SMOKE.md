# Smoke Tests — Security Convergence Batch 1

**Objetivo:** registrar o comportamento "verde" ANTES de aplicar qualquer hardening de segurança.
Executar este checklist **antes** de cada fase e **após** cada deploy. Se algum item regredir,
acionar rollback imediato (ver `RUNBOOK.md` na mesma pasta).

**Última execução baseline:** _preencher data/hora + responsável aqui antes do Fase 1._

---

## Pré-requisitos

- Acesso ao painel admin de produção (`https://helpdesk.thor.<dominio>`).
- 1 grupo WhatsApp de teste cadastrado e ativo no Z-API.
- Conta `atendente` e conta `administrador` válidas (não usar o seed `admin@helpdesk.com.br`).
- `curl` + `jq` instalados localmente.

---

## Checklist (executar em ordem)

### 1. Autenticação
- [ ] **1.1** Login `administrador` via UI → redireciona para dashboard.
- [ ] **1.2** Login `atendente` via UI → aba "Cadastros" **não aparece**.
- [ ] **1.3** Login com senha errada → mensagem genérica de erro, sem stack trace.
- [ ] **1.4** `GET /api/v1/auth/me` com token válido retorna `{id, email, role}`.

### 2. Webhook Z-API → ticket
- [ ] **2.1** Enviar `#chamado teste smoke` no grupo de teste WhatsApp.
- [ ] **2.2** Ticket aparece no Kanban em até 10s, coluna "Aberto".
- [ ] **2.3** Protocolo gerado segue padrão `YYYY-NNNNN`.
- [ ] **2.4** `client_id` e `group_id` corretos no payload do ticket.

### 3. Recebimento de mídia
- [ ] **3.1** Enviar imagem no grupo de teste após o `#chamado`.
- [ ] **3.2** Mensagem aparece no TicketDrawer com thumbnail renderizado.
- [ ] **3.3** Clicar na imagem abre fullscreen sem erro 401/403.
- [ ] **3.4** Áudio: enviar, validar player.
- [ ] **3.5** Documento (PDF): enviar, validar link de download.

### 4. Resposta saindo
- [ ] **4.1** Pelo TicketDrawer, enviar texto → mensagem chega no WhatsApp em até 5s.
- [ ] **4.2** Enviar texto com emoji/acentos → preservados.

### 5. CRUD AdminPanel
- [ ] **5.1** Criar cliente novo → aparece na lista.
- [ ] **5.2** Editar cliente → mudanças persistem.
- [ ] **5.3** Deletar cliente de teste → some da lista (cascade ok).
- [ ] **5.4** Mesmas 3 operações para Grupos WhatsApp.
- [ ] **5.5** Mesmas 3 operações para Agentes (sem deletar a si mesmo).

### 6. Mudança de status (Kanban)
- [ ] **6.1** Mover ticket Aberto → Em atendimento (drag).
- [ ] **6.2** Como `atendente`, transições proibidas devem ficar desabilitadas.
- [ ] **6.3** Como `administrador`, deletar ticket de teste funciona.

### 7. Credenciais cofre (Vault)
- [ ] **7.1** Cadastrar credencial de teste para um cliente.
- [ ] **7.2** Listar credenciais → aparece (mas senha mascarada).
- [ ] **7.3** Revelar senha → valor original retorna intacto.

### 8. Health
- [ ] **8.1** `GET /health` → `200 {"status":"ok"}` (rota raiz, não sob /api/v1).
- [ ] **8.2** `docker compose ps` no VPS → todos serviços `Up (healthy)`.

---

## Critério de aceite

**TODOS** os itens marcados em uma execução = baseline válida.
Se qualquer item falhar **antes** da Fase 1, abrir issue e adiar deploy.
Se qualquer item falhar **após** deploy de uma fase, rollback imediato.
