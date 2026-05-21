import type {
  Agent,
  AgentMe,
  AgentRole,
  Client,
  ClientEmployee,
  ClientAccessCredential,
  ClientAccessCredentialCreated,
  ClientAccessCredentialReveal,
  EmployeeRole,
  KanbanColumn,
  PublicTicket,
  Ticket,
  TicketDetail,
  TicketMessage,
  WhatsAppGroup
} from "../types/api";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

let token = localStorage.getItem("helpdesk_token") ?? "";

function headers() {
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...headers(), ...(options.headers ?? {}) }
  });
  if (!response.ok) {
    const text = await response.text();
    if (response.status === 401 && text.includes("Invalid token")) {
      logout();
      window.dispatchEvent(new Event("auth:expired"));
    }
    throw new Error(text || `Erro HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function login(email: string, password: string) {
  const response = await request<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  token = response.access_token;
  localStorage.setItem("helpdesk_token", token);
}

export function logout() {
  token = "";
  localStorage.removeItem("helpdesk_token");
}

export function hasToken() {
  return Boolean(token);
}

export function getMe() {
  return request<AgentMe>("/auth/me");
}

export function changeOwnPassword(current_password: string, new_password: string) {
  return request<AgentMe>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password })
  });
}

export function getKanban() {
  return request<KanbanColumn[]>("/tickets/kanban");
}

export function getTicket(ticketId: number) {
  return request<TicketDetail>(`/tickets/${ticketId}`);
}

export function assignTicket(ticketId: number) {
  return request(`/tickets/${ticketId}/assign`, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function changeStatus(ticketId: number, status: string) {
  return request(`/tickets/${ticketId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export function replyTicket(ticketId: number, message: string) {
  return request<TicketMessage>(`/tickets/${ticketId}/reply`, {
    method: "POST",
    body: JSON.stringify({ message })
  });
}

export function linkPendingMessage(pendingId: number, ticketId: number) {
  return request<TicketMessage>(`/tickets/pending/${pendingId}/link/${ticketId}`, {
    method: "POST"
  });
}

export function createTicketFromPending(
  pendingId: number,
  payload: { title?: string | null; description?: string | null } = {}
) {
  return request<Ticket>(`/tickets/pending/${pendingId}/create-ticket`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function ignorePendingMessage(pendingId: number) {
  return fetch(`${API_URL}/tickets/pending/${pendingId}/ignore`, {
    method: "POST",
    headers: headers()
  }).then(async (r) => {
    if (!r.ok) throw new Error((await r.text()) || "Falha ao ignorar mensagem");
  });
}

export function getPublicTicket(token: string) {
  return request<PublicTicket>(`/public/tickets/${encodeURIComponent(token)}`);
}

export async function sendPublicTicketMessage(
  token: string,
  message: string,
  files: File[] = []
): Promise<PublicTicket> {
  // Backend espera multipart/form-data (Fase A do portal de uploads).
  // NAO setar Content-Type manualmente — o browser injeta com boundary.
  const form = new FormData();
  form.append("message", message);
  for (const file of files) {
    form.append("files", file, file.name);
  }
  const response = await fetch(
    `${API_URL}/public/tickets/${encodeURIComponent(token)}/messages`,
    { method: "POST", body: form }
  );
  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail = (data && data.detail) || "";
    } catch {
      detail = await response.text().catch(() => "");
    }
    throw new Error(detail || `Falha ao enviar mensagem (HTTP ${response.status})`);
  }
  return response.json();
}

export function getClients() {
  return request<Client[]>("/admin/clients");
}

export function createClient(payload: { name: string; document?: string | null; cnpj?: string | null; is_active?: boolean }) {
  return request<Client>("/admin/clients", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getWhatsAppGroups() {
  return request<WhatsAppGroup[]>("/admin/whatsapp-groups");
}

export function createWhatsAppGroup(payload: {
  client_id: number;
  group_id: string;
  name: string;
  is_active?: boolean;
}) {
  return request<WhatsAppGroup>("/admin/whatsapp-groups", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getAgents() {
  return request<Agent[]>("/admin/agents");
}

export function getEmployeeRoles() {
  return request<EmployeeRole[]>("/admin/employee-roles");
}

export function createEmployeeRole(payload: {
  name: string;
  description?: string | null;
  is_active?: boolean;
}) {
  return request<EmployeeRole>("/admin/employee-roles", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateEmployeeRole(
  id: number,
  payload: Partial<{ name: string; description: string | null; is_active: boolean }>
) {
  return request<EmployeeRole>(`/admin/employee-roles/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteEmployeeRole(id: number) {
  return fetch(`${API_URL}/admin/employee-roles/${id}`, {
    method: "DELETE",
    headers: headers()
  }).then(async (r) => {
    if (!r.ok) throw new Error((await r.text()) || "Falha ao excluir");
  });
}

export function getClientEmployees() {
  return request<ClientEmployee[]>("/admin/client-employees");
}

export function createClientEmployee(payload: {
  whatsapp_group_id: number;
  role_id?: number | null;
  name: string;
  phone: string;
  email?: string | null;
  notes?: string | null;
  is_active?: boolean;
}) {
  return request<ClientEmployee>("/admin/client-employees", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateClientEmployee(
  id: number,
  payload: Partial<{
    whatsapp_group_id: number;
    role_id: number | null;
    name: string;
    phone: string;
    email: string | null;
    notes: string | null;
    is_active: boolean;
  }>
) {
  return request<ClientEmployee>(`/admin/client-employees/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteClientEmployee(id: number) {
  return fetch(`${API_URL}/admin/client-employees/${id}`, {
    method: "DELETE",
    headers: headers()
  }).then(async (r) => {
    if (!r.ok) throw new Error((await r.text()) || "Falha ao excluir");
  });
}

export function createAgent(payload: {
  name: string;
  email: string;
  phone?: string | null;
  password: string;
  role?: AgentRole;
  is_active?: boolean;
}) {
  return request<Agent>("/admin/agents", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateClient(id: number, payload: Partial<{ name: string; document: string | null; cnpj: string | null; is_active: boolean }>) {
  return request<Client>(`/admin/clients/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteClient(id: number) {
  return fetch(`${API_URL}/admin/clients/${id}`, { method: "DELETE", headers: headers() }).then(
    async (r) => { if (!r.ok) throw new Error((await r.text()) || "Falha ao excluir"); }
  );
}

export function updateWhatsAppGroup(
  id: number,
  payload: Partial<{ client_id: number; group_id: string; name: string; is_active: boolean }>
) {
  return request<WhatsAppGroup>(`/admin/whatsapp-groups/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteWhatsAppGroup(id: number) {
  return fetch(`${API_URL}/admin/whatsapp-groups/${id}`, { method: "DELETE", headers: headers() }).then(
    async (r) => { if (!r.ok) throw new Error((await r.text()) || "Falha ao excluir"); }
  );
}

export function updateAgent(
  id: number,
  payload: Partial<{
    name: string;
    email: string;
    phone: string | null;
    password: string;
    role: AgentRole;
    is_active: boolean;
  }>
) {
  return request<Agent>(`/admin/agents/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteAgent(id: number) {
  return fetch(`${API_URL}/admin/agents/${id}`, { method: "DELETE", headers: headers() }).then(
    async (r) => { if (!r.ok) throw new Error((await r.text()) || "Falha ao excluir"); }
  );
}

export function deleteTicket(id: number) {
  return fetch(`${API_URL}/tickets/${id}`, { method: "DELETE", headers: headers() }).then(
    async (r) => { if (!r.ok) throw new Error((await r.text()) || "Falha ao excluir"); }
  );
}

export function getClientAccessCredentials() {
  return request<ClientAccessCredential[]>("/admin/client-access-credentials");
}

export function createClientAccessCredential(payload: {
  client_id: number;
  title: string;
  access_url?: string | null;
  username?: string | null;
  secret: string;
  notes?: string | null;
}) {
  return request<ClientAccessCredentialCreated>("/admin/client-access-credentials", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function revealClientAccessCredential(id: number, reveal_token: string) {
  return request<ClientAccessCredentialReveal>(`/admin/client-access-credentials/${id}/reveal`, {
    method: "POST",
    body: JSON.stringify({ reveal_token })
  });
}

export function deleteClientAccessCredential(id: number) {
  return fetch(`${API_URL}/admin/client-access-credentials/${id}`, { method: "DELETE", headers: headers() }).then(
    async (r) => { if (!r.ok) throw new Error((await r.text()) || "Falha ao excluir"); }
  );
}

export function updateTicket(
  id: number,
  payload: Partial<{ title: string; description: string; priority: string; category_id: number | null }>
) {
  return request<Ticket>(`/tickets/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}
