# THOR-HelpDesk SaaS

Aplicação HelpDesk da THOR Consultoria para equipes de suporte ERP TOTVS Linha WinThor, com abertura automática de tickets a partir de mensagens de grupos WhatsApp recebidas por webhook da Z-API.

## Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Banco: PostgreSQL
- Frontend: React, TypeScript, TailwindCSS
- Deploy: Docker Compose

## Fluxo WhatsApp

1. Cadastre um cliente e associe o `group_id` externo da Z-API na tabela `whatsapp_groups`.
2. Configure o webhook da Z-API para enviar mensagens para:

```text
https://SEU_DOMINIO/api/v1/webhooks/zapi
```

3. Quando uma mensagem do grupo começar com `#chamado`, o backend cria um ticket com protocolo automático.
4. O sistema responde automaticamente no grupo com o protocolo criado e a orientação de uso do comando `#ticket PROTOCOLO`.
5. Mensagens com `#ticket PROTOCOLO` entram diretamente no ticket referenciado.
6. Mensagens sem gatilho ficam pendentes no painel para o atendente vincular ao ticket atual, criar um novo ticket ou ignorar.
7. O atendente pode assumir, mudar status e responder ao grupo pelo painel.

## Subir localmente

```bash
cp .env.example .env
docker compose up --build
```

Acesse:

- Frontend: `http://localhost:8080`
- Backend OpenAPI: `http://localhost:8000/docs`

Login inicial (criado pelo script `scripts/bootstrap_admin.py` no
primeiro `docker compose up`, somente se ainda não houver admin no DB):

- Defina antes de subir:
  ```
  INITIAL_ADMIN_EMAIL=seu.admin@exemplo.com
  INITIAL_ADMIN_PASSWORD=alguma-senha-bem-forte-12-chars-min
  ```
- O agente é criado com `must_change_password=true`; troque na primeira sessão.
- Em ambientes onde o admin já existe, o script é no-op.

Grupo inicial para testes:

- `group_id`: `5585999999999-group`

Payload mínimo para testar o webhook:

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/zapi \
  -H 'Content-Type: application/json' \
  -d '{
    "messageId": "msg-1",
    "chatId": "5585999999999-group",
    "senderPhone": "5585988887777",
    "senderName": "Cliente Teste",
    "text": "#chamado Erro ao emitir NF-e na rotina 1452"
  }'
```

## Instalação em VPS

1. Instale Docker e Docker Compose Plugin.

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

2. Copie o projeto para a VPS e crie o arquivo `.env`.

```bash
cp .env.example .env
nano .env
```

Troque pelo menos:

- `POSTGRES_PASSWORD`
- `JWT_SECRET_KEY`
- `ZAPI_BASE_URL`
- `ZAPI_INSTANCE_ID`
- `ZAPI_TOKEN`
- `ZAPI_CLIENT_TOKEN`, apenas se o painel da Z-API exibir um Client-Token separado

Mapeamento dos campos da Z-API/Postman:

```text
BASE_URL / API da instância          -> ZAPI_BASE_URL
INSTANCE_ID / ID da instância        -> ZAPI_INSTANCE_ID
INSTANCE_TOKEN / Token da instância  -> ZAPI_TOKEN
```

Se a Z-API não mostrar `Client-Token` ou `API key`, deixe `ZAPI_CLIENT_TOKEN` vazio.

A coleção pública do Postman monta as URLs assim:

```text
{{BASE_URL}}/instances/{{INSTANCE_ID}}/token/{{INSTANCE_TOKEN}}/send-text
```
- `CORS_ORIGINS`

3. Suba os serviços.

```bash
docker compose up -d --build
docker compose logs -f backend
```

4. Coloque um proxy reverso na frente, como Nginx ou Traefik, apontando o domínio para a porta do frontend (`8080` por padrão). O Nginx do frontend já encaminha `/api/` para o backend dentro da rede Docker. Por segurança, o Compose publica PostgreSQL e backend apenas em `127.0.0.1`.

5. Configure na Z-API o webhook de mensagens recebidas apontando para o domínio público:

```text
https://SEU_DOMINIO/api/v1/webhooks/zapi
```

## Migrações e seed inicial

O container backend executa automaticamente:

```bash
alembic upgrade head
```

Para rodar manualmente:

```bash
docker compose exec backend alembic upgrade head
```

A migração inicial também cria dados mínimos de demonstração: cliente, grupo WhatsApp, categorias e atendente administrador. O arquivo `db/init/01_seed.sql` contém o mesmo seed em SQL para consulta ou carga manual.

## Estrutura

```text
app/api            endpoints FastAPI
app/core           configuração, banco e segurança
app/models         modelos SQLAlchemy
app/repositories   consultas ao banco
app/schemas        contratos Pydantic
app/services       regras de negócio e integrações
frontend/src/pages tela principal
frontend/src/components componentes do painel
db/init            seed inicial do PostgreSQL
```

## Observações de produção

- O webhook atual é público; adicione validação de token/assinatura se a Z-API do seu plano fornecer segredo por webhook.
- Cadastros administrativos de clientes, grupos e atendentes ainda podem ser feitos por SQL ou por endpoints futuros.
- A URL de envio da Z-API pode variar conforme contrato/plano; ajuste `app/services/zapi.py` se sua instância usar rota diferente.
