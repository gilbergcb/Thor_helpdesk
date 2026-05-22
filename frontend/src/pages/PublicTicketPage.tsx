import {
  ClipboardEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { CheckCircle2, FileText, Paperclip, Send, X } from "lucide-react";

import {
  getPublicTicket,
  getPublicTicketByCode,
  resolvePublicTicket,
  resolvePublicTicketByCode,
  sendPublicTicketMessage,
  sendPublicTicketMessageByCode
} from "../services/api";
import type { PublicTicket, PublicTicketAttachment } from "../types/api";

type Props = {
  token: string;
  mode?: "token" | "code";
};

const statusLabels: Record<string, string> = {
  novo: "novo",
  triagem: "triagem",
  em_atendimento: "em atendimento",
  aguardando_cliente: "aguardando cliente",
  resolvido: "resolvido",
  fechado: "fechado"
};

// Espelha ALLOWED_UPLOAD_MIMES do backend (app/services/media_storage.py).
// Mantenha sincronizado.
const ALLOWED_MIMES = new Set<string>([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
  "application/pdf",
  "text/plain",
  "text/csv",
  "application/json"
]);

const MAX_BYTES = 15 * 1024 * 1024; // 15 MB por arquivo
const MAX_FILES = 3; // por request
const ACCEPT_ATTR =
  "image/png,image/jpeg,image/webp,image/gif,application/pdf,text/plain,text/csv,application/json,.png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.csv,.json";

type Pending = {
  id: string; // local-only (uuid-ish)
  file: File;
  previewUrl: string | null; // object URL para imagens
};

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function isImageMime(mime: string): boolean {
  return mime.startsWith("image/");
}

function randomId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function classifyFile(file: File): string | null {
  if (file.size === 0) return "arquivo vazio";
  if (file.size > MAX_BYTES) {
    return `arquivo maior que ${MAX_BYTES / (1024 * 1024)} MB`;
  }
  // type pode vir vazio (browser não detectou) — backend ainda valida via libmagic;
  // mas se vier conhecido e fora da whitelist, bloqueia já aqui.
  if (file.type && !ALLOWED_MIMES.has(file.type)) {
    return `tipo nao suportado: ${file.type}`;
  }
  return null;
}

function AttachmentBadge({ attachment }: { attachment: PublicTicketAttachment }) {
  const sizeLabel = formatBytes(attachment.byte_size);
  if (isImageMime(attachment.mime_type)) {
    return (
      <a
        className="thor-public-attachment is-image"
        href={attachment.url}
        rel="noopener noreferrer"
        target="_blank"
        title={attachment.original_filename ?? `imagem ${attachment.id}`}
      >
        <img alt={attachment.original_filename ?? "anexo"} src={attachment.url} />
        <span>{sizeLabel}</span>
      </a>
    );
  }
  return (
    <a
      className="thor-public-attachment is-file"
      href={attachment.url}
      rel="noopener noreferrer"
      target="_blank"
      download={attachment.original_filename ?? `anexo-${attachment.id}`}
    >
      <FileText size={18} />
      <div>
        <strong>{attachment.original_filename ?? `anexo-${attachment.id}`}</strong>
        <small>{sizeLabel}</small>
      </div>
    </a>
  );
}

export function PublicTicketPage({ token, mode = "token" }: Props) {
  const [ticket, setTicket] = useState<PublicTicket | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // limpa object URLs ao desmontar ou trocar a lista
  useEffect(() => {
    return () => {
      pending.forEach((p) => p.previewUrl && URL.revokeObjectURL(p.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const canSend = useMemo(() => {
    if (busy) return false;
    if (pending.length > 0) return true;
    return Boolean(message.trim());
  }, [busy, message, pending.length]);

  async function load() {
    setError("");
    try {
      const next =
        mode === "code" ? await getPublicTicketByCode(token) : await getPublicTicket(token);
      setTicket(next);
    } catch {
      setError("Link inválido, expirado ou chamado já finalizado.");
    }
  }

  useEffect(() => {
    load().catch(() => setError("Não foi possível carregar o chamado."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function appendFiles(incoming: FileList | File[]) {
    const arr = Array.from(incoming);
    if (!arr.length) return;
    const errors: string[] = [];
    setPending((current) => {
      const next = [...current];
      for (const file of arr) {
        if (next.length >= MAX_FILES) {
          errors.push(`Máximo de ${MAX_FILES} arquivos por envio`);
          break;
        }
        const reason = classifyFile(file);
        if (reason) {
          errors.push(`${file.name || "arquivo"}: ${reason}`);
          continue;
        }
        next.push({
          id: randomId(),
          file,
          previewUrl: isImageMime(file.type) ? URL.createObjectURL(file) : null
        });
      }
      return next;
    });
    if (errors.length) {
      setError(errors.join(" • "));
    } else {
      setError("");
    }
  }

  function removePending(id: string) {
    setPending((current) => {
      const target = current.find((p) => p.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return current.filter((p) => p.id !== id);
    });
  }

  function clearPending() {
    setPending((current) => {
      current.forEach((p) => p.previewUrl && URL.revokeObjectURL(p.previewUrl));
      return [];
    });
  }

  function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const items = event.clipboardData?.items;
    if (!items) return;
    const files: File[] = [];
    for (const item of Array.from(items)) {
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }
    if (files.length === 0) return; // só texto, deixa o textarea processar normal
    event.preventDefault();
    appendFiles(files);
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function onFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    if (event.target.files) appendFiles(event.target.files);
    event.target.value = ""; // permite escolher o mesmo arquivo de novo se removeu
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSend) return;
    setBusy(true);
    setError("");
    try {
      const files = pending.map((p) => p.file);
      const next =
        mode === "code"
          ? await sendPublicTicketMessageByCode(token, message.trim(), files)
          : await sendPublicTicketMessage(token, message.trim(), files);
      setTicket(next);
      setMessage("");
      clearPending();
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Não foi possível enviar a mensagem.";
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  async function handleResolve() {
    if (!ticket) return;
    if (!confirm(`Marcar o chamado ${ticket.protocol} como resolvido?`)) return;
    setBusy(true);
    setError("");
    try {
      const next =
        mode === "code"
          ? await resolvePublicTicketByCode(token)
          : await resolvePublicTicket(token);
      setTicket(next);
      clearPending();
      setMessage("");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Não foi possível resolver o chamado.";
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  const remainingSlots = MAX_FILES - pending.length;
  const isTerminal = ticket?.status === "resolvido" || ticket?.status === "fechado";

  return (
    <main className="thor-public-page">
      <section className="thor-public-shell">
        <header className="thor-public-header">
          <img alt="THOR Consultoria" src="/assets/logo-thor-1.png" />
          <span>Portal do chamado</span>
        </header>

        {error ? <div className="thor-public-error">{error}</div> : null}

        {ticket ? (
          <>
            <div className="thor-public-summary">
              <div>
                <span className="smallcaps">Protocolo</span>
                <h1>{ticket.protocol}</h1>
              </div>
              <span className={`thor-tag ${ticket.status}`}>
                <span className="dot" />
                {statusLabels[ticket.status] ?? ticket.status}
              </span>
              <p>{ticket.title}</p>
              <dl>
                <div>
                  <dt>Cliente</dt>
                  <dd>{ticket.client_name}</dd>
                </div>
                <div>
                  <dt>Grupo</dt>
                  <dd>{ticket.group_name}</dd>
                </div>
                <div>
                  <dt>Solicitante</dt>
                  <dd>{ticket.requester_name ?? "Cliente"}</dd>
                </div>
                <div>
                  <dt>Atendente</dt>
                  <dd>
                    {ticket.assigned_agent?.name ?? "Aguardando atendimento"}
                    {ticket.assigned_agent?.phone ? (
                      <small>{ticket.assigned_agent.phone}</small>
                    ) : null}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="thor-public-thread">
              {ticket.messages.map((item) => {
                const isAgent = item.direction === "outbound";
                return (
                  <article className={isAgent ? "is-agent" : "is-client"} key={item.id}>
                    <span>{isAgent ? "Atendimento THOR" : "Cliente"}</span>
                    {item.content ? <p>{item.content}</p> : null}
                    {item.attachments && item.attachments.length > 0 ? (
                      <div className="thor-public-attachments">
                        {item.attachments.map((att) => (
                          <AttachmentBadge attachment={att} key={att.id} />
                        ))}
                      </div>
                    ) : null}
                    <time>{new Date(item.created_at).toLocaleString("pt-BR")}</time>
                  </article>
                );
              })}
            </div>

            {isTerminal ? (
              <div className="thor-public-composer">
                <div className="thor-public-error">
                  Chamado finalizado. O link não aceita novas interações.
                </div>
              </div>
            ) : (
              <form className="thor-public-composer" onSubmit={handleSubmit}>
                <textarea
                  onChange={(event) => setMessage(event.target.value)}
                  onPaste={handlePaste}
                  placeholder="Digite sua mensagem ou cole um print com Ctrl+V..."
                  value={message}
                />

                <div className="thor-public-composer-toolbar">
                  <button
                    className="thor-btn-ghost"
                    disabled={busy || remainingSlots <= 0}
                    onClick={openFilePicker}
                    title={
                      remainingSlots > 0
                        ? `Anexar arquivo (até ${remainingSlots} restante${remainingSlots === 1 ? "" : "s"})`
                        : "Limite de arquivos atingido"
                    }
                    type="button"
                  >
                    <Paperclip size={16} /> Anexar
                  </button>
                  <small>
                    Aceita PNG, JPG, WebP, GIF, PDF, TXT, CSV, JSON • até 15 MB por arquivo • máximo 3
                  </small>
                  <input
                    accept={ACCEPT_ATTR}
                    multiple
                    onChange={onFileChange}
                    ref={fileInputRef}
                    style={{ display: "none" }}
                    type="file"
                  />
                </div>

                {pending.length > 0 ? (
                  <ul className="thor-public-composer-pending">
                    {pending.map((p) => (
                      <li className={isImageMime(p.file.type) ? "is-image" : "is-file"} key={p.id}>
                        {p.previewUrl ? (
                          <img alt={p.file.name} src={p.previewUrl} />
                        ) : (
                          <FileText size={20} />
                        )}
                        <div>
                          <strong title={p.file.name}>{p.file.name}</strong>
                          <small>{formatBytes(p.file.size)}</small>
                        </div>
                        <button
                          aria-label={`Remover ${p.file.name}`}
                          className="thor-public-composer-remove"
                          disabled={busy}
                          onClick={() => removePending(p.id)}
                          type="button"
                        >
                          <X size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}

                <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                  <button className="thor-btn" disabled={!canSend} type="submit">
                    <Send size={16} /> Enviar mensagem
                  </button>
                  <button
                    className="thor-btn secondary"
                    disabled={busy}
                    onClick={handleResolve}
                    type="button"
                  >
                    <CheckCircle2 size={16} /> Marcar como resolvido
                  </button>
                </div>
              </form>
            )}
          </>
        ) : null}
      </section>
    </main>
  );
}
