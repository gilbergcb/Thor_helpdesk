import { Eye, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  getClientAccessCredentials,
  revealClientAccessCredential
} from "../services/api";
import type {
  ClientAccessCredential,
  ClientAccessCredentialReveal
} from "../types/api";

export function AccessVaultPanel() {
  const [accesses, setAccesses] = useState<ClientAccessCredential[]>([]);
  const [revealTokenById, setRevealTokenById] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<ClientAccessCredentialReveal | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [activeAccessId, setActiveAccessId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  const filteredAccesses = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return accesses;

    return accesses.filter((access) =>
      [
        access.client.name,
        access.title,
        access.access_url ?? "",
        access.username ?? ""
      ]
        .join(" ")
        .toLowerCase()
        .includes(term)
    );
  }, [accesses, query]);

  async function load() {
    setLoading(true);
    try {
      setAccesses(await getClientAccessCredentials());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar acessos");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function revealAccess(id: number) {
    const revealToken = revealTokenById[id]?.trim();
    if (!revealToken) {
      setError("Informe o token de visualização deste acesso.");
      return;
    }
    setBusyId(id);
    setError("");
    setRevealed(null);
    try {
      const secret = await revealClientAccessCredential(id, revealToken);
      setActiveAccessId(id);
      setRevealed(secret);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Token inválido");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="thor-access-page px-8 py-6 thor-stagger">
      <div className="thor-access-header">
        <span
          className="font-display tnum"
          style={{
            fontStyle: "italic",
            fontSize: 13,
            color: "var(--ink-mute)",
            minWidth: 56
          }}
        >
          iv.
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
          Acessos dos clientes
        </h2>
        <span className="foot-italic thor-access-header-note">
          Consulte com token de visualização
        </span>
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

      {revealed ? (
        <RevealSummary revealed={revealed} onClose={() => setRevealed(null)} />
      ) : null}

      <div className="thor-access-toolbar">
        <div>
          <div className="smallcaps">Cofre de acessos</div>
          <p className="thor-access-toolbar-copy">
            {loading
              ? "Carregando acessos..."
              : `${filteredAccesses.length} de ${accesses.length} acesso${
                  accesses.length === 1 ? "" : "s"
                } encontrado${filteredAccesses.length === 1 ? "" : "s"}`}
          </p>
        </div>
        <label className="thor-access-search">
          <Search size={15} />
          <input
            aria-label="Buscar acesso de cliente"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar cliente, acesso, host ou usuário"
            value={query}
          />
        </label>
      </div>

      <div className="thor-access-layout">
        <div className="thor-access-table-shell">
          <div className="thor-access-table-scroll">
            <table className="thor-access-table">
            <thead>
              <tr>
                {["Cliente", "Acesso", "URL / Host", "Usuário", "Token"].map(
                  (label) => (
                    <th
                      key={label}
                      className="smallcaps"
                      style={{
                        textAlign: "left",
                        padding: "13px 16px",
                        borderBottom: "1px solid var(--hairline)"
                      }}
                    >
                      {label}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {filteredAccesses.map((access) => (
                <tr
                  className={activeAccessId === access.id ? "is-selected" : undefined}
                  key={access.id}
                >
                  <td style={cellStyle} data-label="Cliente">{access.client.name}</td>
                  <td style={cellStyle} data-label="Acesso">{access.title}</td>
                  <td style={cellStyle} data-label="URL / Host">
                    <code>{maskHost(access.access_url)}</code>
                  </td>
                  <td style={cellStyle} data-label="Usuário">
                    <code>{access.username || "—"}</code>
                  </td>
                  <td style={cellStyle} data-label="Token">
                    <div className="thor-access-token-row">
                      <input
                        aria-label={`Token de visualização para ${access.title}`}
                        className="thor-access-token-input"
                        onChange={(event) =>
                          setRevealTokenById({
                            ...revealTokenById,
                            [access.id]: event.target.value
                          })
                        }
                        placeholder="token"
                        type="password"
                        value={revealTokenById[access.id] ?? ""}
                      />
                      <button
                        className="thor-icon-btn"
                        disabled={busyId === access.id}
                        onClick={() => revealAccess(access.id)}
                        title="Visualizar acesso"
                        type="button"
                      >
                        <Eye size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!loading && !filteredAccesses.length ? (
                <tr>
                  <td
                    className="foot-italic"
                    colSpan={5}
                    style={{ padding: 28, textAlign: "center" }}
                  >
                    — vazio —
                  </td>
                </tr>
              ) : null}
              {loading ? (
                <tr>
                  <td
                    className="foot-italic"
                    colSpan={5}
                    style={{ padding: 28, textAlign: "center" }}
                  >
                    Carregando acessos...
                  </td>
                </tr>
              ) : null}
            </tbody>
            </table>
          </div>
          <div className="thor-access-cards">
            {filteredAccesses.map((access) => (
              <article
                className={`thor-card thor-access-card${
                  activeAccessId === access.id ? " is-active" : ""
                }`}
                key={`card-${access.id}`}
              >
                <div className="thor-access-card-grid">
                  <SecretLine label="Cliente" value={access.client.name} plain />
                  <SecretLine label="Acesso" value={access.title} plain />
                  <SecretLine label="URL / Host" value={maskHost(access.access_url)} />
                  <SecretLine label="Usuário" value={access.username} />
                </div>
                <div className="thor-access-card-actions">
                  <input
                    aria-label={`Token de visualização para ${access.title}`}
                    className="thor-access-token-input"
                    onChange={(event) =>
                      setRevealTokenById({
                        ...revealTokenById,
                        [access.id]: event.target.value
                      })
                    }
                    placeholder="token de visualização"
                    type="password"
                    value={revealTokenById[access.id] ?? ""}
                  />
                  <button
                    className="thor-btn sm"
                    disabled={busyId === access.id}
                    onClick={() => revealAccess(access.id)}
                    type="button"
                  >
                    <Eye size={14} />
                    Visualizar
                  </button>
                </div>
              </article>
            ))}
            {!loading && !filteredAccesses.length ? (
              <div className="foot-italic thor-access-empty">— vazio —</div>
            ) : null}
            {loading ? (
              <div className="foot-italic thor-access-empty">
                Carregando acessos...
              </div>
            ) : null}
          </div>
        </div>

      </div>

    </section>
  );
}

function maskHost(value: string | null): string {
  if (!value) return "—";
  return "•".repeat(Math.min(Math.max(value.length, 6), 16));
}

const cellStyle = {
  borderBottom: "1px solid var(--hairline)",
  padding: "13px 16px",
  verticalAlign: "middle"
} as const;

function SecretLine({
  label,
  value,
  plain = false
}: {
  label: string;
  value: string | null;
  plain?: boolean;
}) {
  return (
    <div>
      <div className="smallcaps" style={{ marginBottom: 4 }}>
        {label}
      </div>
      {plain ? <span>{value || "—"}</span> : <code>{value || "—"}</code>}
    </div>
  );
}

function RevealSummary({
  revealed,
  onClose
}: {
  revealed: ClientAccessCredentialReveal;
  onClose: () => void;
}) {
  return (
    <div className="thor-access-reveal-panel" role="status">
      <div className="thor-access-reveal-head">
        <div>
          <div className="smallcaps">Acesso liberado</div>
          <h3 className="font-display">{revealed.title}</h3>
        </div>
        <button
          aria-label="Fechar acesso liberado"
          className="thor-icon-btn"
          onClick={onClose}
          title="Fechar"
          type="button"
        >
          <X size={14} />
        </button>
      </div>
      <div className="thor-access-secret-grid compact">
        <SecretLine label="URL / Host" value={revealed.access_url} />
        <SecretLine label="Usuário" value={revealed.username} />
        <SecretLine label="Segredo" value={revealed.secret} />
        <SecretLine label="Observações" value={revealed.notes} plain />
      </div>
    </div>
  );
}
