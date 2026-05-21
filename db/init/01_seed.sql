-- Seed de DEMO (clientes, grupo whatsapp, categorias).
-- Este arquivo é referência manual; em produção a migração inicial Alembic
-- já popula categorias. Admin NÃO é mais criado por seed — use o script
-- scripts/bootstrap_admin.py via env INITIAL_ADMIN_EMAIL/PASSWORD.

INSERT INTO clients (id, name, document, is_active)
VALUES (1, 'Cliente Demonstração WinThor', '00000000000191', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO whatsapp_groups (id, client_id, group_id, name, is_active)
VALUES (1, 1, '5585999999999-group', 'Suporte WinThor - Cliente Demonstração', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO categories (id, name, description)
VALUES
  (1, 'Fiscal', 'Rotinas fiscais e faturamento'),
  (2, 'Financeiro', 'Contas a pagar, receber e conciliação'),
  (3, 'Estoque', 'Entradas, saídas e inventário')
ON CONFLICT (id) DO NOTHING;
