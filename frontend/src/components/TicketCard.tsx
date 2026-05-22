import type { Ticket } from "../types/api";

type Props = {
  ticket: Ticket;
  selected: boolean;
  onSelect: (ticket: Ticket) => void;
};

const statusLabels: Record<string, string> = {
  novo: "Novo",
  triagem: "Triagem",
  em_atendimento: "Em atendimento",
  aguardando_cliente: "Aguardando cliente",
  resolvido: "Resolvido",
  fechado: "Fechado"
};

const priorityLabels: Record<string, string> = {
  baixa: "— baixa",
  media: "— média",
  alta: "↑ alta",
  critica: "↑ crítica"
};

function initialsOf(name?: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffMs = Date.now() - then;
  const min = Math.round(diffMs / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `há ${hr} h`;
  const d = Math.round(hr / 24);
  return `há ${d} d`;
}

export function TicketCard({ ticket, selected, onSelect }: Props) {
  const status = ticket.status ?? "novo";
  const clientName = ticket.client?.name ?? "Cliente";
  const groupName = ticket.whatsapp_group?.name ?? "";
  const requesterName = ticket.requester?.name ?? ticket.requester?.phone ?? "";
  const agentName = ticket.assigned_agent?.name ?? "";
  return (
    <button
      className={`thor-card ${selected ? "is-active" : ""} text-left`}
      onClick={() => onSelect(ticket)}
      style={{
        padding: "12px 12px 10px",
        cursor: "pointer",
        width: "100%",
        display: "block"
      }}
      type="button"
    >
      <div className="flex items-center justify-between">
        <span
          className="font-display tnum"
          style={{
            fontSize: 11,
            fontStyle: "italic",
            color: "var(--ink-mute)",
            letterSpacing: "0.02em"
          }}
        >
          № {ticket.protocol}
        </span>
        <span className={`thor-tag ${status}`}>
          <span className="dot" />
          {statusLabels[status] ?? status}
        </span>
      </div>

      <h3
        className="font-display"
        style={{
          fontSize: 15,
          lineHeight: 1.3,
          margin: "6px 0 10px",
          letterSpacing: "-0.01em",
          color: "var(--ink)"
        }}
      >
        {ticket.title}
      </h3>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: 12,
          color: "var(--ink-soft)"
        }}
      >
        <span className="thor-avatar xs">{initialsOf(clientName)}</span>
        <div style={{ overflow: "hidden" }}>
          <div
            style={{
              fontWeight: 500,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis"
            }}
          >
            {clientName}
          </div>
          {groupName ? (
            <div
              className="font-display"
              style={{
                color: "var(--ink-mute)",
                fontStyle: "italic",
                fontSize: 11,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis"
              }}
            >
              {groupName}
            </div>
          ) : null}
          {requesterName ? (
            <div
              style={{
                fontSize: 11,
                color: "var(--ink-mute)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis"
              }}
            >
              {requesterName}
            </div>
          ) : null}
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginTop: 10,
          paddingTop: 8,
          borderTop: "1px dashed var(--hairline)",
          fontSize: 11,
          color: "var(--ink-mute)"
        }}
      >
        <span className={`priority ${ticket.priority ?? ""}`}>
          {priorityLabels[ticket.priority ?? "media"] ?? "— média"}
        </span>
        <span
          style={{
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            textAlign: "right"
          }}
          title={agentName ? `Atendente: ${agentName}` : relativeTime(ticket.opened_at)}
        >
          {agentName ? `Atendente: ${agentName}` : relativeTime(ticket.opened_at)}
        </span>
      </div>
    </button>
  );
}
