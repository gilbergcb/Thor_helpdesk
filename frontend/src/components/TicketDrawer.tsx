import { Download, FileText, Link2, LogIn, Plus, Send, Trash2, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  assignTicket,
  changeStatus,
  createTicketFromPending,
  deleteTicket,
  fetchTicketAttachmentBlobUrl,
  getTicket,
  ignorePendingMessage,
  linkPendingMessage,
  replyTicket
} from "../services/api";
import type {
  AgentMe,
  Ticket,
  TicketAttachment,
  TicketDetail,
  TicketStatus
} from "../types/api";

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function AttachmentTile({ attachment }: { attachment: TicketAttachment }) {
  const isImage = attachment.mime_type.startsWith("image/");
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isImage) return;
    let cancelled = false;
    let createdUrl: string | null = null;
    setLoading(true);
    fetchTicketAttachmentBlobUrl(attachment.id)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        createdUrl = url;
        setBlobUrl(url);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Falha ao carregar anexo");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [attachment.id, isImage]);

  async function openFileBlob() {
    setLoading(true);
    setError(null);
    try {
      const url = await fetchTicketAttachmentBlobUrl(attachment.id);
      window.open(url, "_blank", "noopener,noreferrer");
      // best-effort revoke depois de 60s (deixa o tab abrir)
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao abrir anexo");
    } finally {
      setLoading(false);
    }
  }

  const label =
    attachment.original_filename ??
    (isImage ? `imagem-${attachment.id}` : `anexo-${attachment.id}`);
  const sizeLabel = formatBytes(attachment.byte_size);

  if (isImage) {
    return (
      <div
        style={{
          border: "1px solid var(--hairline)",
          background: "var(--bg-elev)",
          padding: 4,
          maxWidth: 200
        }}
        title={`${label} · ${sizeLabel}`}
      >
        {blobUrl ? (
          <a href={blobUrl} rel="noopener noreferrer" target="_blank">
            <img
              alt={label}
              src={blobUrl}
              style={{ display: "block", width: "100%", height: "auto" }}
            />
          </a>
        ) : (
          <div
            style={{
              fontSize: 11,
              color: "var(--ink-mute)",
              padding: 8,
              textAlign: "center"
            }}
          >
            {error ?? (loading ? "carregando..." : "—")}
          </div>
        )}
        <div
          style={{
            fontSize: 10.5,
            color: "var(--ink-mute)",
            padding: "4px 2px 0",
            display: "flex",
            justifyContent: "space-between",
            gap: 6
          }}
        >
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap"
            }}
          >
            {label}
          </span>
          <span>{sizeLabel}</span>
        </div>
      </div>
    );
  }

  return (
    <button
      disabled={loading}
      onClick={openFileBlob}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        border: "1px solid var(--hairline)",
        background: "var(--bg-elev)",
        padding: "8px 10px",
        cursor: loading ? "wait" : "pointer",
        textAlign: "left",
        minWidth: 200,
        maxWidth: 320
      }}
      title={error ?? `${label} · ${sizeLabel}`}
      type="button"
    >
      <FileText size={18} style={{ flex: "none", color: "var(--ink-soft)" }} />
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
        <strong
          style={{
            fontSize: 12,
            fontWeight: 500,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap"
          }}
        >
          {label}
        </strong>
        <small style={{ fontSize: 10.5, color: "var(--ink-mute)" }}>
          {error ?? sizeLabel}
        </small>
      </div>
      <Download size={14} style={{ flex: "none", color: "var(--ink-mute)" }} />
    </button>
  );
}

type Props = {
  ticket: Ticket | null;
  onChanged: () => void;
  onClose?: () => void;
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

export function TicketDrawer({ ticket, onChanged, onClose, viewer }: Props) {
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
        className="thor-ticket-drawer is-empty"
        style={{
          padding: 24
        }}
      >
        <button
          className="thor-ticket-close"
          onClick={onClose}
          title="Fechar painel"
          type="button"
        >
          <X size={16} />
        </button>
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
      className="thor-ticket-drawer"
    >
      {/* Head */}
      <div
        className="thor-ticket-head"
        style={{
          borderBottom: "1px solid var(--hairline)"
        }}
      >
        <button
          className="thor-ticket-close"
          onClick={onClose}
          title="Fechar painel"
          type="button"
        >
          <X size={16} />
        </button>
        <div
          className="thor-ticket-titlebar"
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
              fontSize: "clamp(26px, 2.4vw, 36px)",
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
          className="thor-ticket-meta-grid"
          style={{
            display: "grid",
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
          <div>
            <div className="smallcaps">Atendente</div>
            <div style={{ fontSize: 13, color: "var(--ink)" }}>
              {detail?.assigned_agent?.name ?? ticket.assigned_agent?.name ?? "—"}
            </div>
            {(detail?.assigned_agent?.phone ?? ticket.assigned_agent?.phone) ? (
              <div
                className="font-display"
                style={{ fontSize: 11, fontStyle: "italic", color: "var(--ink-mute)" }}
              >
                {detail?.assigned_agent?.phone ?? ticket.assigned_agent?.phone}
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
        className="thor-ticket-thread"
        style={{
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
                  {message.attachments && message.attachments.length > 0 ? (
                    <div
                      style={{
                        marginTop: 8,
                        display: "flex",
                        flexWrap: "wrap",
                        gap: 8
                      }}
                    >
                      {message.attachments.map((att) => (
                        <AttachmentTile attachment={att} key={att.id} />
                      ))}
                    </div>
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
