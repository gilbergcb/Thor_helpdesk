import { Eye, Pencil, Trash2 } from "lucide-react";
import { FormEvent, ReactNode, useEffect, useState } from "react";

import {
  createAgent,
  createClientEmployee,
  createClientAccessCredential,
  createClient,
  createEmployeeRole,
  createWhatsAppGroup,
  deleteAgent,
  deleteClientEmployee,
  deleteClientAccessCredential,
  deleteClient,
  deleteEmployeeRole,
  deleteWhatsAppGroup,
  getAgents,
  getClientEmployees,
  getClientAccessCredentials,
  getClients,
  getEmployeeRoles,
  getWhatsAppGroups,
  revealClientAccessCredential,
  updateAgent,
  updateClientEmployee,
  updateClient,
  updateEmployeeRole,
  updateWhatsAppGroup
} from "../services/api";
import type {
  Agent,
  AgentRole,
  Client,
  ClientEmployee,
  ClientAccessCredential,
  ClientAccessCredentialReveal,
  EmployeeRole,
  WhatsAppGroup
} from "../types/api";

type Tab = "clients" | "groups" | "employees" | "agents" | "accesses";

const tabLabels: Record<Tab, { num: string; label: string }> = {
  clients: { num: "i.", label: "Clientes" },
  groups: { num: "ii.", label: "Grupos WhatsApp" },
  employees: { num: "iii.", label: "Funcionários" },
  agents: { num: "iv.", label: "Atendentes" },
  accesses: { num: "v.", label: "Acessos" }
};

export function AdminPanel() {
  const [tab, setTab] = useState<Tab>("clients");
  const [clients, setClients] = useState<Client[]>([]);
  const [groups, setGroups] = useState<WhatsAppGroup[]>([]);
  const [roles, setRoles] = useState<EmployeeRole[]>([]);
  const [employees, setEmployees] = useState<ClientEmployee[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [accesses, setAccesses] = useState<ClientAccessCredential[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [clientForm, setClientForm] = useState({ name: "", document: "", cnpj: "" });
  const [groupForm, setGroupForm] = useState({
    client_id: "",
    group_id: "",
    name: ""
  });
  const [agentForm, setAgentForm] = useState<{
    name: string;
    email: string;
    password: string;
    role: AgentRole;
  }>({ name: "", email: "", password: "", role: "atendente" });
  const [roleForm, setRoleForm] = useState({ name: "", description: "" });
  const [employeeForm, setEmployeeForm] = useState({
    whatsapp_group_id: "",
    role_id: "",
    name: "",
    phone: "",
    email: "",
    notes: ""
  });
  const [accessForm, setAccessForm] = useState({
    client_id: "",
    title: "",
    access_url: "",
    username: "",
    secret: "",
    notes: ""
  });
  const [revealTokenById, setRevealTokenById] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<ClientAccessCredentialReveal | null>(null);
  const [editingClientId, setEditingClientId] = useState<number | null>(null);
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null);
  const [editingRoleId, setEditingRoleId] = useState<number | null>(null);
  const [editingEmployeeId, setEditingEmployeeId] = useState<number | null>(null);
  const [editingAgentId, setEditingAgentId] = useState<number | null>(null);

  async function load() {
    const [clientData, groupData, roleData, employeeData, agentData, accessData] = await Promise.all([
      getClients(),
      getWhatsAppGroups(),
      getEmployeeRoles(),
      getClientEmployees(),
      getAgents(),
      getClientAccessCredentials()
    ]);
    setClients(clientData);
    setGroups(groupData);
    setRoles(roleData);
    setEmployees(employeeData);
    setAgents(agentData);
    setAccesses(accessData);
    if (!groupForm.client_id && clientData[0]) {
      setGroupForm((current) => ({
        ...current,
        client_id: String(clientData[0].id)
      }));
    }
    if (!accessForm.client_id && clientData[0]) {
      setAccessForm((current) => ({
        ...current,
        client_id: String(clientData[0].id)
      }));
    }
    if (!employeeForm.whatsapp_group_id && groupData[0]) {
      setEmployeeForm((current) => ({
        ...current,
        whatsapp_group_id: String(groupData[0].id)
      }));
    }
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submitClient(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        name: clientForm.name.trim(),
        document: clientForm.document.trim() || null,
        cnpj: clientForm.cnpj.trim() || null
      };
      if (editingClientId) {
        await updateClient(editingClientId, payload);
      } else {
        await createClient({
          name: payload.name,
          document: payload.document ?? undefined,
          cnpj: payload.cnpj ?? undefined
        });
      }
      setClientForm({ name: "", document: "", cnpj: "" });
      setEditingClientId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar cliente");
    } finally {
      setBusy(false);
    }
  }

  async function submitAccess(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await createClientAccessCredential({
        client_id: Number(accessForm.client_id),
        title: accessForm.title.trim(),
        access_url: accessForm.access_url.trim() || null,
        username: accessForm.username.trim() || null,
        secret: accessForm.secret,
        notes: accessForm.notes.trim() || null
      });
      setNotice(`Token de visualização gerado: ${created.reveal_token}. Guarde em local seguro; ele não será exibido novamente.`);
      setAccessForm((current) => ({
        client_id: current.client_id,
        title: "",
        access_url: "",
        username: "",
        secret: "",
        notes: ""
      }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar acesso");
    } finally {
      setBusy(false);
    }
  }

  async function revealAccess(id: number) {
    const token = revealTokenById[id]?.trim();
    if (!token) {
      setError("Informe o token de visualização deste acesso.");
      return;
    }
    setBusy(true);
    setError("");
    setRevealed(null);
    try {
      setRevealed(await revealClientAccessCredential(id, token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Token inválido");
    } finally {
      setBusy(false);
    }
  }

  async function removeAccess(id: number) {
    if (!confirm("Excluir este acesso?")) return;
    try {
      await deleteClientAccessCredential(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir");
    }
  }

  async function submitGroup(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        client_id: Number(groupForm.client_id),
        group_id: groupForm.group_id.trim(),
        name: groupForm.name.trim()
      };
      if (editingGroupId) {
        await updateWhatsAppGroup(editingGroupId, payload);
      } else {
        await createWhatsAppGroup(payload);
      }
      setGroupForm((current) => ({
        client_id: current.client_id,
        group_id: "",
        name: ""
      }));
      setEditingGroupId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar grupo");
    } finally {
      setBusy(false);
    }
  }

  async function submitRole(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        name: roleForm.name.trim(),
        description: roleForm.description.trim() || null
      };
      if (editingRoleId) {
        await updateEmployeeRole(editingRoleId, payload);
      } else {
        await createEmployeeRole(payload);
      }
      setRoleForm({ name: "", description: "" });
      setEditingRoleId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar função");
    } finally {
      setBusy(false);
    }
  }

  async function submitEmployee(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        whatsapp_group_id: Number(employeeForm.whatsapp_group_id),
        role_id: employeeForm.role_id ? Number(employeeForm.role_id) : null,
        name: employeeForm.name.trim(),
        phone: employeeForm.phone.trim(),
        email: employeeForm.email.trim() || null,
        notes: employeeForm.notes.trim() || null
      };
      if (editingEmployeeId) {
        await updateClientEmployee(editingEmployeeId, payload);
      } else {
        await createClientEmployee(payload);
      }
      setEmployeeForm((current) => ({
        whatsapp_group_id: current.whatsapp_group_id,
        role_id: "",
        name: "",
        phone: "",
        email: "",
        notes: ""
      }));
      setEditingEmployeeId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar funcionário");
    } finally {
      setBusy(false);
    }
  }

  async function submitAgent(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (editingAgentId) {
        const payload: Record<string, unknown> = {
          name: agentForm.name.trim(),
          email: agentForm.email.trim(),
          role: agentForm.role
        };
        if (agentForm.password) payload.password = agentForm.password;
        await updateAgent(editingAgentId, payload);
      } else {
        await createAgent({
          name: agentForm.name.trim(),
          email: agentForm.email.trim(),
          password: agentForm.password,
          role: agentForm.role
        });
      }
      setAgentForm({ name: "", email: "", password: "", role: "atendente" });
      setEditingAgentId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar atendente");
    } finally {
      setBusy(false);
    }
  }

  async function removeClient(id: number) {
    if (
      !confirm(
        "Excluir este cliente? Tickets e grupos vinculados também serão removidos."
      )
    )
      return;
    try {
      await deleteClient(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir");
    }
  }

  async function removeGroup(id: number) {
    if (!confirm("Excluir este grupo WhatsApp?")) return;
    try {
      await deleteWhatsAppGroup(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir");
    }
  }

  async function removeRole(id: number) {
    if (!confirm("Excluir esta função?")) return;
    try {
      await deleteEmployeeRole(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir");
    }
  }

  async function removeEmployee(id: number) {
    if (!confirm("Excluir este funcionário?")) return;
    try {
      await deleteClientEmployee(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir");
    }
  }

  async function removeAgentRow(id: number) {
    if (!confirm("Excluir este atendente?")) return;
    try {
      await deleteAgent(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir");
    }
  }

  return (
    <section className="thor-admin-page px-8 py-6 thor-stagger">
      {/* Header / page title */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 24,
          borderBottom: "1px solid var(--hairline)",
          paddingBottom: 14,
          marginBottom: 24
        }}
      >
        <span
          className="font-display tnum"
          style={{
            fontStyle: "italic",
            fontSize: 13,
            color: "var(--ink-mute)",
            minWidth: 56
          }}
        >
          {tabLabels[tab].num}
        </span>
        <h2
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: 26,
            margin: 0,
            letterSpacing: "-0.015em"
          }}
        >
          Cadastros
        </h2>
        <span className="foot-italic" style={{ marginLeft: "auto" }}>
          Clientes · grupos WhatsApp · atendentes
        </span>
      </div>

      {/* Tabs */}
      <div
        className="thor-tabs"
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid var(--hairline)",
          marginBottom: 24
        }}
      >
        {(Object.keys(tabLabels) as Tab[]).map((key) => {
          const isOn = tab === key;
          return (
            <button
              className="font-display"
              key={key}
              onClick={() => setTab(key)}
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: "12px 22px 14px",
                color: isOn ? "var(--ink)" : "var(--ink-mute)",
                fontSize: 14,
                letterSpacing: "0.01em",
                borderBottom: isOn
                  ? "1px solid var(--accent)"
                  : "1px solid transparent",
                marginBottom: -1,
                transition: "color .2s, border-color .2s"
              }}
              type="button"
            >
              <em
                style={{
                  fontStyle: "italic",
                  marginRight: 6,
                  color: "var(--ink-mute)",
                  fontSize: 11
                }}
              >
                {tabLabels[key].num}
              </em>
              {tabLabels[key].label}
            </button>
          );
        })}
      </div>

      {error ? (
        <div
          className="foot-italic"
          style={{
            border: "1px solid color-mix(in srgb, var(--danger) 40%, var(--hairline))",
            background:
              "color-mix(in srgb, var(--danger-soft) 50%, transparent)",
            color: "var(--danger)",
            padding: "10px 14px",
            marginBottom: 18,
            fontStyle: "normal"
          }}
        >
          {error}
        </div>
      ) : null}

      {tab === "clients" ? (
        <div className="thor-admin-split">
          <FormPanel
            mode={editingClientId ? "Editando" : "Novo"}
            title={editingClientId ? "Editar cliente" : "Novo cliente"}
            onSubmit={submitClient}
            busy={busy}
            onCancel={
              editingClientId
                ? () => {
                    setEditingClientId(null);
                    setClientForm({ name: "", document: "", cnpj: "" });
                  }
                : undefined
            }
            submitLabel={editingClientId ? "Atualizar" : "Salvar cliente"}
          >
            <Field full label="Nome">
              <input
                onChange={(e) =>
                  setClientForm({ ...clientForm, name: e.target.value })
                }
                required
                value={clientForm.name}
              />
            </Field>
            <Field full label="Documento">
              <input
                onChange={(e) =>
                  setClientForm({ ...clientForm, document: e.target.value })
                }
                value={clientForm.document}
              />
            </Field>
            <Field full label="CNPJ">
              <input
                onChange={(e) =>
                  setClientForm({ ...clientForm, cnpj: e.target.value })
                }
                placeholder="00.000.000/0000-00"
                value={clientForm.cnpj}
              />
            </Field>
          </FormPanel>

          <DataTable
            columns={[
              { key: "code", label: "Código", code: true },
              { key: "name", label: "Nome" },
              { key: "document", label: "Documento" },
              { key: "cnpj", label: "CNPJ" },
              { key: "status", label: "Status" }
            ]}
            rows={clients.map((client) => ({
              cells: [
                String(client.id),
                client.name,
                client.document || "—",
                client.cnpj || "—",
                client.is_active ? "Ativo" : "Inativo"
              ],
              raw: client
            }))}
            renderActions={(_row, index) => {
              const client = clients[index];
              return (
                <>
                  <RowButton
                    onClick={() => {
                      setEditingClientId(client.id);
                      setClientForm({
                        name: client.name,
                        document: client.document ?? "",
                        cnpj: client.cnpj ?? ""
                      });
                    }}
                    title="Editar"
                  >
                    <Pencil size={14} />
                  </RowButton>
                  <RowButton
                    danger
                    onClick={() => removeClient(client.id)}
                    title="Excluir"
                  >
                    <Trash2 size={14} />
                  </RowButton>
                </>
              );
            }}
          />
        </div>
      ) : null}

      {tab === "groups" ? (
        <div className="thor-admin-split">
          <FormPanel
            mode={editingGroupId ? "Editando" : "Novo"}
            title={editingGroupId ? "Editar grupo" : "Novo grupo WhatsApp"}
            onSubmit={submitGroup}
            busy={busy}
            onCancel={
              editingGroupId
                ? () => {
                    setEditingGroupId(null);
                    setGroupForm((c) => ({
                      client_id: c.client_id,
                      group_id: "",
                      name: ""
                    }));
                  }
                : undefined
            }
            submitLabel={editingGroupId ? "Atualizar" : "Salvar grupo"}
          >
            <Field full label="Cliente">
              <select
                onChange={(e) =>
                  setGroupForm({ ...groupForm, client_id: e.target.value })
                }
                required
                value={groupForm.client_id}
              >
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field full label="Nome do grupo">
              <input
                onChange={(e) =>
                  setGroupForm({ ...groupForm, name: e.target.value })
                }
                required
                value={groupForm.name}
              />
            </Field>
            <Field full label="Group ID da Z-API">
              <input
                onChange={(e) =>
                  setGroupForm({ ...groupForm, group_id: e.target.value })
                }
                placeholder="120363…-group"
                required
                value={groupForm.group_id}
              />
            </Field>
          </FormPanel>

          <DataTable
            columns={[
              { key: "code", label: "Código", code: true },
              { key: "name", label: "Grupo" },
              { key: "client", label: "Cliente" },
              { key: "gid", label: "Group ID" },
              { key: "status", label: "Status" }
            ]}
            rows={groups.map((group) => ({
              cells: [
                String(group.id),
                group.name,
                group.client.name,
                group.group_id,
                group.is_active ? "Ativo" : "Inativo"
              ],
              raw: group
            }))}
            renderActions={(_row, index) => {
              const group = groups[index];
              return (
                <>
                  <RowButton
                    onClick={() => {
                      setEditingGroupId(group.id);
                      setGroupForm({
                        client_id: String(group.client_id),
                        group_id: group.group_id,
                        name: group.name
                      });
                    }}
                    title="Editar"
                  >
                    <Pencil size={14} />
                  </RowButton>
                  <RowButton
                    danger
                    onClick={() => removeGroup(group.id)}
                    title="Excluir"
                  >
                    <Trash2 size={14} />
                  </RowButton>
                </>
              );
            }}
          />
        </div>
      ) : null}

      {tab === "agents" ? (
        <div className="thor-admin-split">
          <FormPanel
            mode={editingAgentId ? "Editando" : "Novo"}
            title={editingAgentId ? "Editar atendente" : "Novo atendente"}
            onSubmit={submitAgent}
            busy={busy}
            onCancel={
              editingAgentId
                ? () => {
                    setEditingAgentId(null);
                    setAgentForm({
                      name: "",
                      email: "",
                      password: "",
                      role: "atendente"
                    });
                  }
                : undefined
            }
            submitLabel={editingAgentId ? "Atualizar" : "Salvar atendente"}
          >
            <Field full label="Nome">
              <input
                onChange={(e) =>
                  setAgentForm({ ...agentForm, name: e.target.value })
                }
                required
                value={agentForm.name}
              />
            </Field>
            <Field full label="E-mail">
              <input
                onChange={(e) =>
                  setAgentForm({ ...agentForm, email: e.target.value })
                }
                required
                type="email"
                value={agentForm.email}
              />
            </Field>
            <Field
              full
              label={
                editingAgentId
                  ? "Senha (deixe em branco para manter)"
                  : "Senha"
              }
            >
              <input
                minLength={editingAgentId ? 0 : 6}
                onChange={(e) =>
                  setAgentForm({ ...agentForm, password: e.target.value })
                }
                required={!editingAgentId}
                type="password"
                value={agentForm.password}
              />
            </Field>
            <Field full label="Perfil">
              <select
                onChange={(e) =>
                  setAgentForm({
                    ...agentForm,
                    role: e.target.value as AgentRole
                  })
                }
                value={agentForm.role}
              >
                <option value="atendente">Atendente</option>
                <option value="supervisor">Supervisor</option>
                <option value="administrador">Administrador</option>
              </select>
            </Field>
          </FormPanel>

          <DataTable
            columns={[
              { key: "code", label: "Código", code: true },
              { key: "name", label: "Nome" },
              { key: "email", label: "E-mail" },
              { key: "role", label: "Perfil" },
              { key: "status", label: "Status" }
            ]}
            rows={agents.map((agent) => ({
              cells: [
                String(agent.id),
                agent.name,
                agent.email,
                "__perfil__:" + agent.role,
                agent.is_active ? "Ativo" : "Inativo"
              ],
              raw: agent
            }))}
            renderActions={(_row, index) => {
              const agent = agents[index];
              return (
                <>
                  <RowButton
                    onClick={() => {
                      setEditingAgentId(agent.id);
                      setAgentForm({
                        name: agent.name,
                        email: agent.email,
                        password: "",
                        role: agent.role
                      });
                    }}
                    title="Editar"
                  >
                    <Pencil size={14} />
                  </RowButton>
                  <RowButton
                    danger
                    onClick={() => removeAgentRow(agent.id)}
                    title="Excluir"
                  >
                    <Trash2 size={14} />
                  </RowButton>
                </>
              );
            }}
          />
        </div>
      ) : null}

      {tab === "employees" ? (
        <div style={{ display: "grid", gap: 24 }}>
          <div className="thor-admin-split compact-form">
            <FormPanel
              mode={editingRoleId ? "Editando" : "Novo"}
              title={editingRoleId ? "Editar função" : "Nova função"}
              onSubmit={submitRole}
              busy={busy}
              onCancel={
                editingRoleId
                  ? () => {
                      setEditingRoleId(null);
                      setRoleForm({ name: "", description: "" });
                    }
                  : undefined
              }
              submitLabel={editingRoleId ? "Atualizar" : "Salvar função"}
            >
              <Field full label="Nome da função">
                <input
                  onChange={(e) =>
                    setRoleForm({ ...roleForm, name: e.target.value })
                  }
                  required
                  value={roleForm.name}
                />
              </Field>
              <Field full label="Descrição">
                <textarea
                  onChange={(e) =>
                    setRoleForm({ ...roleForm, description: e.target.value })
                  }
                  rows={3}
                  value={roleForm.description}
                />
              </Field>
            </FormPanel>

            <DataTable
              columns={[
                { key: "code", label: "Código", code: true },
                { key: "name", label: "Função" },
                { key: "description", label: "Descrição" },
                { key: "status", label: "Status" }
              ]}
              rows={roles.map((role) => ({
                cells: [
                  String(role.id),
                  role.name,
                  role.description || "—",
                  role.is_active ? "Ativo" : "Inativo"
                ],
                raw: role
              }))}
              renderActions={(_row, index) => {
                const role = roles[index];
                return (
                  <>
                    <RowButton
                      onClick={() => {
                        setEditingRoleId(role.id);
                        setRoleForm({
                          name: role.name,
                          description: role.description ?? ""
                        });
                      }}
                      title="Editar"
                    >
                      <Pencil size={14} />
                    </RowButton>
                    <RowButton danger onClick={() => removeRole(role.id)} title="Excluir">
                      <Trash2 size={14} />
                    </RowButton>
                  </>
                );
              }}
            />
          </div>

          <div className="thor-admin-split wide-table">
            <FormPanel
              mode={editingEmployeeId ? "Editando" : "Novo"}
              title={editingEmployeeId ? "Editar funcionário" : "Novo funcionário"}
              onSubmit={submitEmployee}
              busy={busy}
              onCancel={
                editingEmployeeId
                  ? () => {
                      setEditingEmployeeId(null);
                      setEmployeeForm((current) => ({
                        whatsapp_group_id: current.whatsapp_group_id,
                        role_id: "",
                        name: "",
                        phone: "",
                        email: "",
                        notes: ""
                      }));
                    }
                  : undefined
              }
              submitLabel={editingEmployeeId ? "Atualizar" : "Salvar funcionário"}
            >
              <Field full label="Grupo WhatsApp">
                <select
                  onChange={(e) =>
                    setEmployeeForm({
                      ...employeeForm,
                      whatsapp_group_id: e.target.value
                    })
                  }
                  required
                  value={employeeForm.whatsapp_group_id}
                >
                  {groups.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.client.name} · {group.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field full label="Função">
                <select
                  onChange={(e) =>
                    setEmployeeForm({ ...employeeForm, role_id: e.target.value })
                  }
                  value={employeeForm.role_id}
                >
                  <option value="">Sem função</option>
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field full label="Nome">
                <input
                  onChange={(e) =>
                    setEmployeeForm({ ...employeeForm, name: e.target.value })
                  }
                  required
                  value={employeeForm.name}
                />
              </Field>
              <Field full label="Telefone">
                <input
                  onChange={(e) =>
                    setEmployeeForm({ ...employeeForm, phone: e.target.value })
                  }
                  placeholder="5511999999999"
                  required
                  value={employeeForm.phone}
                />
              </Field>
              <Field full label="E-mail">
                <input
                  onChange={(e) =>
                    setEmployeeForm({ ...employeeForm, email: e.target.value })
                  }
                  type="email"
                  value={employeeForm.email}
                />
              </Field>
              <Field full label="Observações">
                <textarea
                  onChange={(e) =>
                    setEmployeeForm({ ...employeeForm, notes: e.target.value })
                  }
                  rows={3}
                  value={employeeForm.notes}
                />
              </Field>
            </FormPanel>

            <DataTable
              columns={[
                { key: "code", label: "Código", code: true },
                { key: "name", label: "Funcionário" },
                { key: "role", label: "Função" },
                { key: "client", label: "Cliente" },
                { key: "group", label: "Grupo" },
                { key: "phone", label: "Telefone" }
              ]}
              rows={employees.map((employee) => ({
                cells: [
                  String(employee.id),
                  employee.name,
                  employee.role?.name || "—",
                  employee.client.name,
                  employee.whatsapp_group.name,
                  employee.phone
                ],
                raw: employee
              }))}
              renderActions={(_row, index) => {
                const employee = employees[index];
                return (
                  <>
                    <RowButton
                      onClick={() => {
                        setEditingEmployeeId(employee.id);
                        setEmployeeForm({
                          whatsapp_group_id: String(employee.whatsapp_group_id),
                          role_id: employee.role_id ? String(employee.role_id) : "",
                          name: employee.name,
                          phone: employee.phone,
                          email: employee.email ?? "",
                          notes: employee.notes ?? ""
                        });
                      }}
                      title="Editar"
                    >
                      <Pencil size={14} />
                    </RowButton>
                    <RowButton
                      danger
                      onClick={() => removeEmployee(employee.id)}
                      title="Excluir"
                    >
                      <Trash2 size={14} />
                    </RowButton>
                  </>
                );
              }}
            />
          </div>
        </div>
      ) : null}

      {tab === "accesses" ? (
        <div className="thor-admin-split wide-table">
          <FormPanel
            mode="Cofre"
            title="Novo acesso de cliente"
            onSubmit={submitAccess}
            busy={busy}
            submitLabel="Salvar acesso"
          >
            <Field full label="Cliente">
              <select
                onChange={(e) =>
                  setAccessForm({ ...accessForm, client_id: e.target.value })
                }
                required
                value={accessForm.client_id}
              >
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field full label="Título">
              <input
                onChange={(e) =>
                  setAccessForm({ ...accessForm, title: e.target.value })
                }
                placeholder="Servidor, WinThor, banco, VPN..."
                required
                value={accessForm.title}
              />
            </Field>
            <Field full label="URL / Host">
              <input
                onChange={(e) =>
                  setAccessForm({ ...accessForm, access_url: e.target.value })
                }
                value={accessForm.access_url}
              />
            </Field>
            <Field full label="Usuário">
              <input
                onChange={(e) =>
                  setAccessForm({ ...accessForm, username: e.target.value })
                }
                value={accessForm.username}
              />
            </Field>
            <Field full label="Senha / token / segredo">
              <input
                onChange={(e) =>
                  setAccessForm({ ...accessForm, secret: e.target.value })
                }
                required
                type="password"
                value={accessForm.secret}
              />
            </Field>
            <Field full label="Observações">
              <textarea
                onChange={(e) =>
                  setAccessForm({ ...accessForm, notes: e.target.value })
                }
                rows={3}
                value={accessForm.notes}
              />
            </Field>
          </FormPanel>

          <div style={{ display: "grid", gap: 16 }}>
            {notice ? (
              <div
                className="foot-italic"
                style={{
                  border: "1px solid var(--accent)",
                  padding: "10px 14px",
                  color: "var(--ink)"
                }}
              >
                {notice}
              </div>
            ) : null}
            {revealed ? (
              <div className="thor-card" style={{ padding: 16 }}>
                <div className="font-display" style={{ fontSize: 18 }}>
                  {revealed.title}
                </div>
                <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
                  <strong>URL/Host:</strong> <code>{revealed.access_url || "—"}</code>
                  <strong>Usuário:</strong> <code>{revealed.username || "—"}</code>
                  <strong>Segredo:</strong> <code>{revealed.secret}</code>
                  <strong>Observações:</strong> <span>{revealed.notes || "—"}</span>
                </div>
              </div>
            ) : null}
            <DataTable
              columns={[
                { key: "code", label: "Código", code: true },
                { key: "client", label: "Cliente" },
                { key: "title", label: "Acesso" },
                { key: "user", label: "Usuário" },
                { key: "status", label: "Status" }
              ]}
              rows={accesses.map((access) => ({
                cells: [
                  String(access.id),
                  access.client.name,
                  access.title,
                  access.username || "—",
                  access.is_active ? "Ativo" : "Inativo"
                ],
                raw: access
              }))}
              renderActions={(_row, index) => {
                const access = accesses[index];
                return (
                  <>
                    <input
                      aria-label="Token de visualização"
                      className="thor-admin-token-input"
                      onChange={(e) =>
                        setRevealTokenById({
                          ...revealTokenById,
                          [access.id]: e.target.value
                        })
                      }
                      placeholder="token"
                      type="password"
                      value={revealTokenById[access.id] ?? ""}
                    />
                    <RowButton onClick={() => revealAccess(access.id)} title="Visualizar">
                      <Eye size={14} />
                    </RowButton>
                    <RowButton danger onClick={() => removeAccess(access.id)} title="Excluir">
                      <Trash2 size={14} />
                    </RowButton>
                  </>
                );
              }}
            />
          </div>
        </div>
      ) : null}
    </section>
  );
}

/* ============================================================
   Sub-components
   ============================================================ */

function FormPanel({
  title,
  mode,
  children,
  onSubmit,
  busy,
  submitLabel,
  onCancel
}: {
  title: string;
  mode: string;
  children: ReactNode;
  onSubmit: (e: FormEvent) => void;
  busy: boolean;
  submitLabel: string;
  onCancel?: () => void;
}) {
  return (
    <form
      className="thor-admin-form-panel"
      onSubmit={onSubmit}
    >
      <div className="thor-admin-form-head">
        <div
          className="font-display"
          style={{
            fontStyle: "italic",
            fontSize: 12,
            color: "var(--accent)",
            letterSpacing: "0.04em"
          }}
        >
          {mode}
        </div>
        <h3
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: 22,
            letterSpacing: "-0.015em",
            margin: "4px 0 0"
          }}
        >
          {title}
        </h3>
      </div>
      <div className="thor-admin-form-grid">
        {children}
      </div>
      <div className="thor-admin-form-footer">
        <span className="foot-italic">As alterações são imediatas.</span>
        <div style={{ display: "flex", gap: 10 }}>
          {onCancel ? (
            <button
              className="thor-btn ghost sm"
              onClick={onCancel}
              type="button"
            >
              Cancelar
            </button>
          ) : null}
          <button className="thor-btn sm" disabled={busy} type="submit">
            {submitLabel}
          </button>
        </div>
      </div>
    </form>
  );
}

function Field({
  children,
  label,
  full
}: {
  children: ReactNode;
  label: string;
  full?: boolean;
}) {
  return (
    <label
      className="thor-field"
      style={{ gridColumn: full ? "1 / -1" : undefined, marginBottom: 0 }}
    >
      <span>{label}</span>
      {children}
    </label>
  );
}

type Column = { key: string; label: string; code?: boolean };
type Row = { cells: string[]; raw?: unknown };

function DataTable({
  columns,
  rows,
  renderActions
}: {
  columns: Column[];
  rows: Row[];
  renderActions?: (row: Row, index: number) => ReactNode;
}) {
  const totalCols = columns.length + (renderActions ? 1 : 0);
  return (
    <div
      className="thor-data-table-shell"
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--hairline)",
        boxShadow: "var(--shadow-sm)"
      }}
    >
      <div className="thor-data-table-scroll">
        <table className="thor-table thor-admin-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  className={col.code ? "code" : undefined}
                  key={col.key}
                  style={col.code ? { width: 86 } : undefined}
                >
                  {col.label}
                </th>
              ))}
              {renderActions ? (
                <th className="actions-col" style={{ textAlign: "right" }}>Ações</th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row, index) => (
                <tr key={`${row.cells[0]}-${index}`}>
                  {row.cells.map((cell, cellIndex) => {
                    const col = columns[cellIndex];
                    if (cell.startsWith("__perfil__:")) {
                      const role = cell.split(":")[1];
                      return (
                        <td data-label={col?.label} key={cellIndex}>
                          <span className={`perfil ${role}`}>
                            <span className="dot" />
                            <span>{role}</span>
                          </span>
                        </td>
                      );
                    }
                    return (
                      <td
                        className={col?.code ? "code" : undefined}
                        data-label={col?.label}
                        key={cellIndex}
                      >
                        {cell}
                      </td>
                    );
                  })}
                  {renderActions ? (
                    <td className="right" data-label="Ações">
                      <div className="thor-row-actions">
                        {renderActions(row, index)}
                      </div>
                    </td>
                  ) : null}
                </tr>
              ))
            ) : (
              <tr>
                <td
                  className="foot-italic"
                  colSpan={totalCols}
                  style={{ textAlign: "center", padding: "28px 16px" }}
                >
                  Nenhum registro encontrado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="thor-data-table-cards">
        {rows.length ? (
          rows.map((row, index) => (
            <article className="thor-card thor-data-card" key={`${row.cells[0]}-${index}`}>
              <div className="thor-data-card-grid">
                {row.cells.map((cell, cellIndex) => {
                  const col = columns[cellIndex];
                  if (cell.startsWith("__perfil__:")) {
                    const role = cell.split(":")[1];
                    return (
                      <div key={cellIndex}>
                        <div className="smallcaps">{col?.label}</div>
                        <span className={`perfil ${role}`}>
                          <span className="dot" />
                          <span>{role}</span>
                        </span>
                      </div>
                    );
                  }
                  return (
                    <div key={cellIndex}>
                      <div className="smallcaps">{col?.label}</div>
                      <span className={col?.code ? "tnum" : undefined}>{cell}</span>
                    </div>
                  );
                })}
              </div>
              {renderActions ? (
                <div className="thor-data-card-actions">
                  {renderActions(row, index)}
                </div>
              ) : null}
            </article>
          ))
        ) : (
          <div className="foot-italic thor-data-empty">Nenhum registro encontrado.</div>
        )}
      </div>
    </div>
  );
}

function RowButton({
  onClick,
  title,
  danger,
  children
}: {
  onClick: () => void;
  title: string;
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      className={`thor-ico ${danger ? "danger" : ""}`}
      onClick={onClick}
      title={title}
      type="button"
    >
      {children}
    </button>
  );
}
