export type TicketStatus =
  | "novo"
  | "triagem"
  | "em_atendimento"
  | "aguardando_cliente"
  | "resolvido"
  | "fechado";

export type TicketPriority = "baixa" | "media" | "alta" | "critica";

export type Ticket = {
  id: number;
  protocol: string;
  title: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  opened_at: string;
  closed_at: string | null;
  client: { id: number; name: string };
  whatsapp_group: { id: number; group_id: string; name: string };
  requester:
    | {
        id: number;
        phone: string;
        name: string | null;
        employee_id: number | null;
        employee_role: { id: number; name: string } | null;
      }
    | null;
  assigned_agent: { id: number; name: string; email: string; phone: string | null } | null;
};

export type TicketAttachment = {
  id: number;
  mime_type: string;
  byte_size: number;
  original_filename: string | null;
  source: string;
  url: string;
};

export type TicketMessage = {
  id: number;
  direction: "inbound" | "outbound";
  content: string;
  media_type: string | null;
  media_url: string | null;
  media_mime_type: string | null;
  media_storage_key: string | null;
  local_media_url: string | null;
  attachments: TicketAttachment[];
  created_at: string;
};

export type PublicTicketAttachment = {
  id: number;
  mime_type: string;
  byte_size: number;
  original_filename: string | null;
  source: string;
  url: string;
};

export type PublicTicketMessage = {
  id: number;
  direction: "inbound" | "outbound";
  content: string;
  media_type: string | null;
  media_storage_key: string | null;
  local_media_url: string | null;
  attachments: PublicTicketAttachment[];
  created_at: string;
};

export type PublicTicket = {
  protocol: string;
  title: string;
  status: TicketStatus;
  client_name: string;
  group_name: string;
  requester_name: string | null;
  assigned_agent: { name: string; phone: string | null } | null;
  messages: PublicTicketMessage[];
};

export type PendingTicketMessage = {
  id: number;
  content: string;
  media_type: string | null;
  media_url: string | null;
  media_mime_type: string | null;
  media_storage_key: string | null;
  local_media_url: string | null;
  reason: string | null;
  created_at: string;
  sender:
    | {
        id: number;
        phone: string;
        name: string | null;
        employee_id: number | null;
        employee_role: { id: number; name: string } | null;
      }
    | null;
};

export type TicketDetail = Ticket & {
  messages: TicketMessage[];
  pending_messages: PendingTicketMessage[];
};

export type KanbanColumn = {
  status: TicketStatus;
  tickets: Ticket[];
};

export type Client = {
  id: number;
  name: string;
  document: string | null;
  cnpj: string | null;
  is_active: boolean;
};

export type WhatsAppGroup = {
  id: number;
  client_id: number;
  group_id: string;
  name: string;
  is_active: boolean;
  client: Client;
};

export type AgentRole = "atendente" | "supervisor" | "administrador";

export type Agent = {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  role: AgentRole;
  is_active: boolean;
  must_change_password: boolean;
};

export type AgentMe = {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  role: AgentRole;
  must_change_password: boolean;
};

export type EmployeeRole = {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
};

export type ClientEmployee = {
  id: number;
  whatsapp_group_id: number;
  role_id: number | null;
  name: string;
  phone: string;
  email: string | null;
  notes: string | null;
  is_active: boolean;
  client: Client;
  whatsapp_group: WhatsAppGroup;
  role: EmployeeRole | null;
};

export type ClientAccessCredential = {
  id: number;
  client_id: number;
  title: string;
  access_url: string | null;
  username: string | null;
  is_active: boolean;
  client: Client;
};

export type ClientAccessCredentialCreated = ClientAccessCredential & {
  reveal_token: string;
};

export type ClientAccessCredentialReveal = {
  id: number;
  title: string;
  access_url: string | null;
  username: string | null;
  secret: string;
  notes: string | null;
};

export type ReportOption = {
  id: number;
  name: string;
};

export type AttendanceReportOptions = {
  clients: ReportOption[];
  employees: ReportOption[];
  agents: ReportOption[];
};

export type AttendanceReportSummary = {
  total: number;
  open_total: number;
  resolved_total: number;
  closed_total: number;
  avg_resolution_hours: number | null;
  by_status: Record<string, number>;
};

export type AttendanceReportRow = {
  id: number;
  protocol: string;
  title: string;
  status: TicketStatus;
  priority: TicketPriority;
  opened_at: string;
  closed_at: string | null;
  resolution_hours: number | null;
  client_id: number;
  client_name: string;
  employee_id: number | null;
  employee_name: string | null;
  requester_name: string | null;
  requester_phone: string | null;
  agent_id: number | null;
  agent_name: string | null;
};

export type AttendanceReport = {
  date_from: string;
  date_to: string;
  summary: AttendanceReportSummary;
  tickets: AttendanceReportRow[];
};
