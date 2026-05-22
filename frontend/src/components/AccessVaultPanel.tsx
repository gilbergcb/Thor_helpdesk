import { Eye, Search, X } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useMemo, useState } from "react";

import {
  enableTotp,
  getClientAccessCredentials,
  revealClientAccessCredential,
  setupTotp
} from "../services/api";
import type {
  AgentMe,
  ClientAccessCredential,
  ClientAccessCredentialReveal,
  TotpSetup
} from "../types/api";

export function AccessVaultPanel({
  me,
  onMeChanged
}: {
  me: AgentMe;
  onMeChanged: (agent: AgentMe) => void;
}) {
  const [accesses, setAccesses] = useState<ClientAccessCredential[]>([]);
  const [totpCodeById, setTotpCodeById] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<ClientAccessCredentialReveal | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [activeAccessId, setActiveAccessId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [totpSetup, setTotpSetup] = useState<TotpSetup | null>(null);
  const [totpSetupCode, setTotpSetupCode] = useState("");
  const [totpQrCodeUrl, setTotpQrCodeUrl] = useState("");
  const [totpBusy, setTotpBusy] = useState(false);

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

  useEffect(() => {
    let cancelled = false;
    if (!totpSetup) {
      setTotpQrCodeUrl("");
      return;
    }
    QRCode.toDataURL(totpSetup.provisioning_uri, {
      errorCorrectionLevel: "M",
      margin: 1,
      width: 192,
      color: {
        dark: "#1f1710",
        light: "#fffaf2"
      }
    })
      .then((url) => {
        if (!cancelled) setTotpQrCodeUrl(url);
      })
      .catch(() => {
        if (!cancelled) setTotpQrCodeUrl("");
      });
    return () => {
      cancelled = true;
    };
  }, [totpSetup]);

  async function revealAccess(id: number) {
    const totpCode = totpCodeById[id]?.trim();
    if (!totpCode) {
      setError("Informe o código 1Password deste usuário.");
      return;
    }
    setBusyId(id);
    setError("");
    setRevealed(null);
    try {
      const secret = await revealClientAccessCredential(id, totpCode);
      setActiveAccessId(id);
      setRevealed(secret);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Código inválido");
    } finally {
      setBusyId(null);
    }
  }

  async function startTotpSetup() {
    setTotpBusy(true);
    setError("");
    try {
      setTotpSetup(await setupTotp());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao iniciar 2FA");
    } finally {
      setTotpBusy(false);
    }
  }

  async function finishTotpSetup() {
    const code = totpSetupCode.trim();
    if (!code) {
      setError("Informe o código gerado no 1Password.");
      return;
    }
    setTotpBusy(true);
    setError("");
    try {
      const updated = await enableTotp(code);
      onMeChanged(updated);
      setTotpSetup(null);
      setTotpSetupCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Código inválido");
    } finally {
      setTotpBusy(false);
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
          {me.totp_enabled ? "Consulte com código 1Password" : "Configure 1Password para consultar"}
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

      {!me.totp_enabled ? (
        <div className="thor-access-reveal-panel" style={{ marginBottom: 18 }}>
          <div className="thor-access-reveal-head">
            <div>
              <div className="smallcaps">1Password</div>
              <h3 className="font-display">Ativar código por usuário</h3>
            </div>
            <button
              className="thor-btn sm"
              disabled={totpBusy}
              onClick={startTotpSetup}
              type="button"
            >
              Configurar
            </button>
          </div>
          {totpSetup ? (
            <div className="thor-access-secret-grid compact">
              {totpQrCodeUrl ? (
                <div>
                  <div className="smallcaps" style={{ marginBottom: 4 }}>
                    QR Code
                  </div>
                  <img
                    alt="QR Code para configurar 2FA no Bitwarden ou 1Password"
                    src={totpQrCodeUrl}
                    style={{
                      border: "1px solid var(--hairline)",
                      display: "block",
                      height: 192,
                      width: 192
                    }}
                  />
                </div>
              ) : null}
              <SecretLine label="Chave" value={totpSetup.secret} />
              <SecretLine label="URI" value={totpSetup.provisioning_uri} />
              <div>
                <div className="smallcaps" style={{ marginBottom: 4 }}>
                  Código
                </div>
                <div className="thor-access-token-row">
                  <input
                    className="thor-access-token-input"
                    onChange={(event) => setTotpSetupCode(event.target.value)}
                    placeholder="123456"
                    type="password"
                    value={totpSetupCode}
                  />
                  <button
                    className="thor-btn sm"
                    disabled={totpBusy}
                    onClick={finishTotpSetup}
                    type="button"
                  >
                    Ativar
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
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
                {["Cliente", "Acesso", "URL / Host", "Usuário", "Código"].map(
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
                  <td style={cellStyle} data-label="Código">
                    <div className="thor-access-token-row">
                      <input
                        aria-label={`Código 1Password para ${access.title}`}
                        className="thor-access-token-input"
                        onChange={(event) =>
                          setTotpCodeById({
                            ...totpCodeById,
                            [access.id]: event.target.value
                          })
                        }
                        placeholder="1Password"
                        type="password"
                        value={totpCodeById[access.id] ?? ""}
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
                    aria-label={`Código 1Password para ${access.title}`}
                    className="thor-access-token-input"
                    onChange={(event) =>
                      setTotpCodeById({
                        ...totpCodeById,
                        [access.id]: event.target.value
                      })
                    }
                    placeholder="código 1Password"
                    type="password"
                    value={totpCodeById[access.id] ?? ""}
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
