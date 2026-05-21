import { FormEvent, useEffect, useState } from "react";
import { Send } from "lucide-react";

import { getPublicTicket, sendPublicTicketMessage } from "../services/api";
import type { PublicTicket } from "../types/api";

type Props = {
  token: string;
};

const statusLabels: Record<string, string> = {
  novo: "novo",
  triagem: "triagem",
  em_atendimento: "em atendimento",
  aguardando_cliente: "aguardando cliente",
  resolvido: "resolvido",
  fechado: "fechado"
};

export function PublicTicketPage({ token }: Props) {
  const [ticket, setTicket] = useState<PublicTicket | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try {
      setTicket(await getPublicTicket(token));
    } catch {
      setError("Link inválido, expirado ou chamado já finalizado.");
    }
  }

  useEffect(() => {
    load().catch(() => setError("Não foi possível carregar o chamado."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!message.trim()) return;
    setBusy(true);
    setError("");
    try {
      setTicket(await sendPublicTicketMessage(token, message.trim()));
      setMessage("");
    } catch {
      setError("Não foi possível enviar a mensagem.");
    } finally {
      setBusy(false);
    }
  }

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
                    <p>{item.content}</p>
                    <time>{new Date(item.created_at).toLocaleString("pt-BR")}</time>
                  </article>
                );
              })}
            </div>

            <form className="thor-public-composer" onSubmit={handleSubmit}>
              <textarea
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Digite sua mensagem para o atendimento..."
                value={message}
              />
              <button className="thor-btn" disabled={busy || !message.trim()} type="submit">
                <Send size={16} /> Enviar mensagem
              </button>
            </form>
          </>
        ) : null}
      </section>
    </main>
  );
}
