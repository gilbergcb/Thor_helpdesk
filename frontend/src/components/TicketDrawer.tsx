import { Link2, LogIn, Plus, Send, Trash2, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  assignTicket,
  changeStatus,
  createTicketFromPending,
  deleteTicket,
  getTicket,
  ignorePendingMessage,
  linkPendingMessage,
  replyTicket
} from "../services/api";
import type { AgentMe, Ticket, TicketDetail, TicketStatus } from "../types/api";

type Props = {
  ticket: Ticket | null;
  onChanged: () => void;
  viewer?: AgentMe | null;
};

const nextStatuses: TicketStatus[] = [
  "triagem",
  "em_atendimento",
  "aguardando_cliente",
  "resolvido",
  "fechado"
];

const statusLabels: Record<TicketStatus, string> = {
  novo: "novo",
  triagem: "triagem",
  em_atendimento: "em atendimento",
  aguardando_cliente: "aguardando cliente",
  resolvido: "resolvido",
  fechado: "fechado"
};

function initialsOf(name?: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function splitProtocol(protocol: string): { main: string; suffix: string } {
  // e.g. "20260519-00037" -> main: "20260519", suffix: "·00037"
  const m = protocol.match(/^(.+?)[-.](\d+)$/);
  if (m) return { main: m[1], suffix: `.${m[2]}` };
  return { main: protocol, suffix: "" };
}

export function TicketDrawer({ ticket, onChanged, viewer }: Props) {
  const isAtendente = viewer?.role === "atendente";
  const isAdmin = viewer?.role === "administrador";
  const allowedStatuses = isAtendente
    ? (["triagem", "em_atendimento", "aguardando_cliente", "resolvido"] as TicketStatus[])
    : nextStatuses;

  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ticket) {
      setDetail(null);
      return;
    }
    getTicket(ticket.id).then(setDetail).catch(console.error);
  }, [ticket]);

  async function handleAssign() {
    if (!ticket) return;
    setBusy(true);
    try {
      await assignTicket(ticket.id);
      onChanged();
      setDetail(await getTicket(ticket.id));
    } finally {
      setBusy(false);
    }
  }

  async function handleStatus(status: TicketStatus) {
    if (!ticket) return;
    setBusy(true);
    try {
      await changeStatus(ticket.id, status);
      onChanged();
      setDetail(await getTicket(ticket.id));
    } finally {
      setBusy(false);
    }
  }

  async function handleReply(event: FormEvent) {
    event.preventDefault();
    if (!ticket || !reply.trim()) return;
    setBusy(true);
    try {
      await replyTicket(ticket.id, reply.trim());
      setReply("");
      onChanged();
      setDetail(await getTicket(ticket.id));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!ticket) return;
    if (!confirm(`Excluir definitivamente o ticket ${ticket.protocol}?`)) return;
    setBusy(true);
    try {
      await deleteTicket(ticket.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function handleLinkPending(pendingId: number) {
    if (!ticket) return;
    setBusy(true);
    try {
      await linkPendingMessage(pendingId, ticket.id);
      onChanged();
      setDetail(await getTicket(ticket.id));
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateFromPending(pendingId: number) {
    if (!ticket) return;
    setBusy(true);
    try {
      await createTicketFromPending(pendingId);
      onChanged();
      setDetail(await getTicket(ticket.id));
    } finally {
      setBusy(false);
    }
  }

  async function handleIgnorePending(pendingId: number) {
    if (!ticket) return;
    setBusy(true);
    try {
      await ignorePendingMessage(pendingId);
      onChanged();
      setDetail(await getTicket(ticket.id));
    } finally {
      setBusy(false);
    }
  }

  if (!ticket) {
    return (
      <aside
        style={{
          borderLeft: "1px solid var(--hairline)",
          background: "var(--bg-elev)",
          padding: 24,
          minHeight: "calc(100vh - 84px)"
        }}
      >
        <div
          className="foot-italic"
          style={{
            display: "flex",
            height: "100%",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center"
          }}
        >
          Selecione um ticket no Kanban.
        </div>
      </aside>
    );
  }

  const { main: protoMain, suffix: protoSuffix } = splitProtocol(ticket.protocol);
  const currentStatus = (detail?.status ?? ticket.status) as TicketStatus;

  return (
    <aside
      className="flex flex-col"
      style={{
        borderLeft: "1px solid var(--hairline)",
        background: "var(--bg-elev)",
        boxShadow: "var(--shadow-md)",
        height: "calc(100vh - 84px)"
      }}
    >
      {/* Head */}
      <div
        style={{
          padding: "24px 26px 18px",
          borderBottom: "1px solid var(--hairline)"
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 10
          }}
        >
          <div
            className="font-display tnum"
            style={{
              fontWeight: 500,
              fontSize: "clamp(32px, 4vw, 44px)",
              letterSpacing: "-0.02em",
              lineHeight: 1
            }}
          >
            {protoMain}
            <em
              style={{
                fontStyle: "italic",
                color: "var(--accent)",
                fontWeight: 500,
                fontSize: "0.55em",
                verticalAlign: "0.5em",
                marginLeft: 6
              }}
            >
              {protoSuffix || ".v1"}
            </em>
          </div>
          <span className={`thor-tag ${currentStatus}`}>
            <span className="dot" />
            {statusLabels[currentStatus]}
          </span>
        </div>

        <h2
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: 19,
            lineHeight: 1.25,
            margin: "14px 0",
            letterSpacing: "-0.01em"
          }}
        >
          {ticket.title}
        </h2>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 14,
            paddingTop: 14,
            borderTop: "1px solid var(--hairline)"
          }}
        >
          <div>
            <div className="smallcaps">Cliente</div>
            <div style={{ fontSize: 13, color: "var(--ink)" }}>
              {ticket.client?.name ?? "—"}
            </div>
          </div>
          <div>
            <div className="smallcaps">Grupo</div>
            <div style={{ fontSize: 13, color: "var(--ink)" }}>
              {ticket.whatsapp_group?.name ?? "—"}
            </div>
          </div>
          <div>
            <div className="smallcaps">Prioridade</div>
            <div
              className={`priority ${ticket.priority}`}
              style={{ fontSize: 13 }}
            >
              {ticket.priority}
            </div>
          </div>
          <div>
            <div className="smallcaps">Solicitante</div>
            <div style={{ fontSize: 13, color: "var(--ink)" }}>
              {ticket.requester?.name ?? ticket.requester?.phone ?? "—"}
            </div>
            {ticket.requester?.employee_role?.name ? (
              <div
                className="font-display"
                style={{ fontSize: 11, fontStyle: "italic", color: "var(--ink-mute)" }}
              >
                {ticket.requester.employee_role.name}
              </div>
            ) : null}
          </div>
        </div>

        <div
          style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 18 }}
        >
          <button
            className="thor-btn sm"
            disabled={busy}
            onClick={handleAssign}
            title="Assumir ticket"
            type="button"
          >
            <LogIn size={14} /> Assumir
          </button>
          <select
            disabled={busy}
            onChange={(event) =>
              handleStatus(event.target.value as TicketStatus)
            }
            style={{
              padding: "6px 12px",
              border: "1px solid var(--hairline-strong)",
              background: "var(--bg)",
              color: "var(--ink)",
              fontSize: 12,
              fontFamily: "Geist, sans-serif",
              outline: "none"
            }}
            value={currentStatus}
          >
            {[currentStatus, ...allowedStatuses]
              .filter((v, i, a) => a.indexOf(v) === i)
              .map((status) => (
                <option key={status} value={status}>
                  {statusLabels[status as TicketStatus] ?? status}
                </option>
              ))}
          </select>
          {isAdmin && (
            <button
              className="thor-btn danger-ghost sm"
              disabled={busy}
              onClick={handleDelete}
              title="Excluir ticket"
              type="button"
            >
              <Trash2 size={14} /> Excluir
            </button>
          )}
        </div>
      </div>

      {/* Thread */}
      <div
        style={{
          padding: "22px 26px",
          overflow: "auto",
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: 18
        }}
      >
        {(detail?.messages ?? []).map((message) => {
          const isAgent = message.direction === "outbound";
          const mediaSrc =
            message.local_media_url ?? message.media_url ?? undefined;
          return (
            <div
              key={message.id}
              style={{
                display: "flex",
                gap: 10,
                maxWidth: "88%",
                alignSelf: isAgent ? "flex-end" : "flex-start",
                flexDirection: isAgent ? "row-reverse" : "row"
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 10.5,
                    textTransform: "uppercase",
                    letterSpacing: "0.12em",
                    color: "var(--ink-mute)",
                    marginBottom: 5,
                    justifyContent: isAgent ? "flex-end" : "flex-start"
                  }}
                >
                  <span style={{ color: "var(--ink-soft)", fontWeight: 500 }}>
                    {isAgent ? "Atendente" : "Cliente"}
                  </span>
                  <span
                    className="font-display tnum"
                    style={{
                      fontStyle: "italic",
                      fontSize: 11.5,
                      textTransform: "none",
                      letterSpacing: "0.05em"
                    }}
                  >
                    {new Date(message.created_at).toLocaleString("pt-BR")}
                  </span>
                </div>
                <div
                  style={{
                    border: isAgent
                      ? "1px solid color-mix(in srgb, var(--accent) 25%, var(--hairline))"
                      : "1px solid var(--hairline)",
                    background: isAgent
                      ? "var(--bubble-agent)"
                      : "var(--bubble-client)",
                    padding: "10px 12px",
                    fontSize: 13.5,
                    lineHeight: 1.55,
                    color: "var(--ink)",
                    marginLeft: isAgent ? 24 : 0,
                    marginRight: isAgent ? 0 : 24
                  }}
                >
                  {mediaSrc && message.media_type === "image" ? (
                    <figure
                      style={{
                        margin: "0 0 8px",
                        border: "1px solid var(--hairline-strong)",
                        padding: 4,
                        background: "var(--bg)",
                        display: "inline-block"
                      }}
                    >
                      <a href={mediaSrc} rel="noreferrer" target="_blank">
                        <img
                          alt={message.content || "Imagem"}
                          src={mediaSrc}
                          style={{
                            display: "block",
                            maxWidth: 280,
                            height: "auto"
                          }}
                        />
                      </a>
                      {message.content ? (
                        <figcaption
                          className="font-display"
                          style={{
                            fontStyle: "italic",
                            fontSize: 11,
                            color: "var(--ink-mute)",
                            padding: "6px 4px 2px"
                          }}
                        >
                          {message.content}
                        </figcaption>
                      ) : null}
                    </figure>
                  ) : null}
                  {mediaSrc && message.media_type === "audio" ? (
                    <audio
                      controls
                      src={mediaSrc}
                      style={{ width: "100%", marginBottom: 8 }}
                    />
                  ) : null}
                  {mediaSrc && message.media_type === "video" ? (
                    <video
                      controls
                      src={mediaSrc}
                      style={{
                        width: "100%",
                        maxHeight: 260,
                        border: "1px solid var(--hairline)",
                        marginBottom: 8
                      }}
                    />
                  ) : null}
                  {mediaSrc && message.media_type === "document" ? (
                    <a
                      href={mediaSrc}
                      rel="noreferrer"
                      style={{
                        display: "inline-block",
                        marginBottom: 8,
                        fontSize: 13,
                        color: "var(--accent)",
                        borderBottom:
                          "1px solid color-mix(in srgb, var(--accent) 40%, transparent)"
                      }}
                      target="_blank"
                    >
                      Baixar documento
                    </a>
                  ) : null}
                  {message.media_type !== "image" || !mediaSrc ? (
                    <p
                      style={{
                        margin: 0,
                        whiteSpace: "pre-wrap"
                      }}
                    >
                      {message.content}
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
        {(detail?.messages ?? []).length === 0 ? (
          <div
            className="foot-italic"
            style={{ textAlign: "center", marginTop: 12 }}
          >
            — sem mensagens ainda —
          </div>
        ) : null}
      </div>

      {(detail?.pending_messages ?? []).length > 0 ? (
        <section className="thor-pending-thread">
          <div className="thor-pending-head">
            <div>
              <span className="smallcaps">Mensagens pendentes do grupo</span>
              <strong>{detail?.pending_messages.length ?? 0}</strong>
            </div>
            <p className="foot-italic">
              Vincule ao ticket atual, crie um novo chamado ou ignore.
            </p>
          </div>
          <div className="thor-pending-list">
            {(detail?.pending_messages ?? []).map((pending) => (
              <article className="thor-pending-card" key={pending.id}>
                <div className="thor-pending-meta">
                  <span>{pending.sender?.name ?? pending.sender?.phone ?? "Cliente"}</span>
                  <time>{new Date(pending.created_at).toLocaleString("pt-BR")}</time>
                </div>
                <p>{pending.content}</p>
                {pending.reason ? <small>{pending.reason}</small> : null}
                <div className="thor-pending-actions">
                  <button
                    className="thor-btn sm"
                    disabled={busy}
                    onClick={() => handleLinkPending(pending.id)}
                    title="Vincular ao ticket selecionado"
                    type="button"
                  >
                    <Link2 size={14} /> Vincular aqui
                  </button>
                  <button
                    className="thor-btn ghost sm"
                    disabled={busy}
                    onClick={() => handleCreateFromPending(pending.id)}
                    title="Criar novo ticket a partir desta mensagem"
                    type="button"
                  >
                    <Plus size={14} /> Novo ticket
                  </button>
                  <button
                    className="thor-btn danger-ghost sm"
                    disabled={busy}
                    onClick={() => handleIgnorePending(pending.id)}
                    title="Ignorar mensagem pendente"
                    type="button"
                  >
                    <X size={14} /> Ignorar
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {/* Composer */}
      <form
        className="thor-composer"
        onSubmit={handleReply}
        style={{
          borderTop: "1px solid var(--hairline)",
          padding: "14px 20px 18px",
          display: "flex",
          flexDirection: "column",
          gap: 10,
          background: "color-mix(in srgb, var(--bg) 50%, var(--bg-elev))"
        }}
      >
        <textarea
          onChange={(event) => setReply(event.target.value)}
          placeholder="Responder no grupo WhatsApp…"
          value={reply}
        />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between"
          }}
        >
          <span className="foot-italic">
            {initialsOf(viewer?.name)} · resposta editorial
          </span>
          <button
            className="thor-btn sm"
            disabled={busy || !reply.trim()}
            title="Enviar resposta"
            type="submit"
          >
            <Send size={14} /> Enviar
          </button>
        </div>
      </form>
    </aside>
  );
}
