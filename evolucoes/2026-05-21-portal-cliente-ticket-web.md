# Evolucao: Portal web do cliente por ticket

Data: 2026-05-21
Status: Proposta
Prioridade sugerida: Alta

## Contexto

O THOR-HelpDesk hoje usa o WhatsApp como porta de entrada e tambem como canal de interacao do atendimento. Esse fluxo funciona para abertura rapida de chamados, mas pode poluir os grupos quando existem muitos tickets simultaneos, mensagens complementares, anexos, validacoes e respostas de atendentes.

A evolucao proposta transforma o WhatsApp em canal de notificacao e abertura, enquanto a conversa detalhada do ticket passa a acontecer em uma pagina web segura.

## Objetivos

- Reduzir mensagens empilhadas nos grupos WhatsApp dos clientes.
- Permitir que o usuario acompanhe e interaja com o atendimento em uma pagina web.
- Reutilizar o cadastro de funcionarios do cliente, vinculados a telefone e grupo WhatsApp.
- Permitir visao restrita: usuario do cliente ve apenas seus proprios tickets.
- Permitir perfil gestor do cliente para visualizar tickets da empresa.
- Coletar confirmacao de resolucao e nivel de satisfacao.
- Controlar tickets que dependem de suporte TOTVS antes do fechamento definitivo.

## Visao geral da solucao

Quando um usuario enviar no grupo:

```text
#chamado erro na rotina 1452
```

O sistema cria o ticket e responde no grupo com protocolo e link:

```text
Chamado aberto: 20260521-00002

Acompanhe e interaja com o atendimento pelo link:
https://helpdesk.thorconsultoria.com.br/t/abc123...

Nossa equipe vai conduzir o atendimento por la.
```

O grupo passa a receber somente mensagens importantes:

- ticket criado;
- atendente assumiu;
- ticket enviado para suporte TOTVS;
- retorno de resolucao aguardando validacao;
- ticket fechado.

As mensagens detalhadas ficam no portal web do ticket.

## Escopo funcional

### Fase 1 - Link publico seguro do ticket

Criar um link unico por ticket, acessivel sem login, com token aleatorio.

Regras:

- O token deve ser gerado automaticamente na criacao do ticket.
- O token deve ficar ativo enquanto o ticket nao estiver fechado.
- O token pode expirar ou ser revogado manualmente.
- O token nao deve ser salvo em texto puro no banco, apenas hash.
- O link deve permitir visualizar e responder somente aquele ticket.

Rotas sugeridas:

```text
GET  /t/:token
POST /api/v1/public/tickets/:token/messages
POST /api/v1/public/tickets/:token/resolve-confirmation
```

Modelo sugerido:

```text
ticket_public_links
- id
- ticket_id
- token_hash
- expires_at
- revoked_at
- last_access_at
- created_at
- updated_at
```

### Fase 2 - Portal do funcionario do cliente

Criar login para funcionario do cliente usando o cadastro ja existente.

Perfis sugeridos:

```text
usuario_cliente
- ve somente os tickets abertos por ele
- pode responder os seus tickets
- pode confirmar resolucao
- pode avaliar atendimento

gestor_cliente
- ve todos os tickets do cliente
- pode acompanhar chamados dos funcionarios da empresa
- pode responder tickets se permitido
```

Campos novos sugeridos em `client_employees`:

```text
portal_role: usuario_cliente | gestor_cliente
portal_enabled: boolean
password_hash: string nullable
last_login_at: datetime nullable
must_change_password: boolean
```

Rotas sugeridas:

```text
POST /api/v1/client-auth/login
GET  /api/v1/client-auth/me
GET  /api/v1/client/tickets
GET  /api/v1/client/tickets/:id
POST /api/v1/client/tickets/:id/messages
```

### Fase 3 - Conversa web do ticket

A tela web do ticket deve conter:

- protocolo;
- status;
- cliente;
- grupo WhatsApp de origem;
- solicitante;
- atendente responsavel;
- historico de mensagens;
- anexos;
- campo de resposta;
- botao de confirmacao de resolucao;
- botao para indicar que ainda precisa de ajuda.

As mensagens devem indicar origem:

```text
message_source
- whatsapp
- attendant_panel
- client_portal
- system
```

Alteracao sugerida em `ticket_messages`:

```text
source: whatsapp | attendant_panel | client_portal | system
```

### Fase 4 - Confirmacao de resolucao e satisfacao

Quando o atendente marcar o ticket como resolvido, o cliente recebe a solicitacao de validacao.

Fluxo:

```text
Atendente marca como resolvido
-> Cliente recebe link para validar
-> Cliente escolhe "Resolvido" ou "Ainda preciso de ajuda"
```

Se o cliente confirmar:

- coletar nota de 1 a 5;
- coletar comentario opcional;
- fechar o ticket.

Se o cliente negar:

- reabrir ticket;
- voltar para `em_atendimento`;
- registrar historico.

Modelo sugerido:

```text
ticket_feedback
- id
- ticket_id
- resolved_confirmed
- rating
- comment
- responded_at
- created_at
```

### Fase 5 - Escalonamento TOTVS

Alguns chamados precisam de suporte da TOTVS. O ticket THOR nao deve ser fechado antes da solucao ou retorno definitivo da TOTVS.

Campos sugeridos:

```text
ticket_totvs_escalations
- id
- ticket_id
- totvs_ticket_number
- status: aberto | aguardando_totvs | respondido | resolvido | cancelado
- opened_at
- resolved_at
- notes
- created_at
- updated_at
```

Regras:

- Um ticket pode ser marcado como "depende de TOTVS".
- O ticket THOR nao pode ser fechado enquanto a escalacao TOTVS estiver aberta.
- O atendente registra o numero do chamado TOTVS.
- Quando a TOTVS retornar, o atendente registra a solucao.
- Depois disso, o ticket volta para validacao do cliente.

Fluxo sugerido:

```text
Novo
-> Em atendimento
-> Aguardando TOTVS
-> Retorno TOTVS recebido
-> Resolvido aguardando cliente
-> Fechado
```

Observacao: preferir substatus TOTVS inicialmente, em vez de criar um novo status principal no Kanban. Isso reduz impacto visual e operacional.

## Mudancas de interface

### Painel do atendente

Adicionar no detalhe do ticket:

- botao "Copiar link do cliente";
- indicador "Link ativo";
- aba "Portal do cliente";
- aba ou bloco "Escalonamento TOTVS";
- campo "Numero do chamado TOTVS";
- status da escalacao TOTVS;
- historico de validacao do cliente;
- nota de satisfacao.

### Portal publico do ticket

Tela simples e responsiva:

- topo com marca THOR;
- protocolo em destaque;
- status atual;
- conversa;
- campo de resposta;
- anexos;
- botao "Foi resolvido";
- botao "Ainda preciso de ajuda".

### Portal autenticado do cliente

Telas:

```text
/cliente/login
/cliente/tickets
/cliente/tickets/:id
```

Filtros:

- abertos;
- em atendimento;
- aguardando cliente;
- resolvidos;
- fechados.

## Seguranca

- Token publico deve ser longo, aleatorio e salvo apenas como hash.
- Link publico nao deve expor outros tickets do cliente.
- Link publico deve ser revogado no fechamento do ticket.
- Acesso autenticado de funcionario deve respeitar cliente, grupo e perfil.
- Anexos devem continuar protegidos por rota controlada.
- Registrar `last_access_at` e eventos relevantes.

## Criterios de aceite

- Ao abrir um ticket por WhatsApp, o grupo recebe um link web do ticket.
- O link permite visualizar historico e enviar mensagem para o ticket.
- Mensagem enviada pelo portal aparece no painel do atendente.
- Atendente consegue responder pelo painel e a resposta aparece no portal.
- Usuario comum do cliente nao ve tickets de outros usuarios.
- Gestor do cliente ve tickets da empresa.
- Cliente consegue confirmar resolucao ou reabrir atendimento.
- Cliente consegue avaliar atendimento com nota de 1 a 5.
- Ticket com escalacao TOTVS aberta nao pode ser fechado.
- Atendente consegue registrar numero e status do chamado TOTVS.

## Plano recomendado de implementacao

1. Implementar link publico seguro por ticket.
2. Criar tela `/t/:token` com conversa e resposta.
3. Enviar link automaticamente na abertura do ticket.
4. Adicionar origem das mensagens (`source`).
5. Implementar confirmacao de resolucao e satisfacao.
6. Implementar login do funcionario do cliente.
7. Implementar perfil gestor do cliente.
8. Implementar escalonamento TOTVS.

## Riscos e cuidados

- Evitar que link publico vire acesso amplo aos dados do cliente.
- Nao transformar o WhatsApp em espelho completo da conversa web, para nao voltar a poluir o grupo.
- Nao fechar tickets com pendencia TOTVS.
- Manter boa rastreabilidade no historico do ticket.
- Garantir que usuarios vinculados por telefone sejam associados ao cliente correto.

## Fora do escopo inicial

- Chat em tempo real com WebSocket.
- App mobile.
- Integracao direta com API da TOTVS.
- SLA avancado por contrato.
- Base de conhecimento automatica.
