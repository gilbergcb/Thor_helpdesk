import { FileBarChart, KeyRound, LogOut, Moon, RefreshCcw, Sun } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { KanbanBoard } from "../components/KanbanBoard";
import { AdminPanel } from "../components/AdminPanel";
import { AccessVaultPanel } from "../components/AccessVaultPanel";
import { ReportsPanel } from "../components/ReportsPanel";
import { TicketDrawer } from "../components/TicketDrawer";
import { PublicTicketPage } from "./PublicTicketPage";
import { useTheme } from "../hooks/useTheme";
import {
  changeOwnPassword,
  getKanban,
  getMe,
  hasToken,
  login,
  logout
} from "../services/api";
import type { AgentMe, KanbanColumn, Ticket } from "../types/api";

function initialsOf(name?: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      aria-label="Alternar tema"
      className="thor-icon-btn"
      onClick={toggleTheme}
      title={theme === "light" ? "Modo escuro" : "Modo claro"}
      type="button"
    >
      {theme === "light" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

function Login({ onLogged }: { onLogged: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      onLogged();
    } catch {
      setError("E-mail ou senha inválidos.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      className="grid min-h-screen place-items-center px-4 py-10"
      style={{ background: "var(--bg)" }}
    >
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div
        className="w-full max-w-md border thor-stagger"
        style={{
          borderColor: "var(--hairline)",
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-md)"
        }}
      >
        <div className="px-10 pt-12 pb-2 text-center">
          <img
            alt="THOR Consultoria"
            className="thor-login-logo"
            src="/assets/logo-thor-1.png"
          />
          <div className="smallcaps" style={{ marginTop: 10 }}>
            HelpDesk · Suporte WinThor — TOTVS
          </div>
        </div>

        <div className="divider-asterisk" style={{ margin: "20px 0 8px" }}>
          * &nbsp; * &nbsp; *
        </div>

        <form className="px-10 pb-10" onSubmit={handleSubmit}>
          <h1
            className="font-display"
            style={{
              fontSize: "26px",
              fontWeight: 500,
              letterSpacing: "-0.02em",
              margin: "0 0 4px"
            }}
          >
            Bem-vindo de volta.
          </h1>
          <p
            style={{
              color: "var(--ink-mute)",
              margin: "0 0 24px",
              fontSize: 13
            }}
          >
            Entre com sua conta corporativa Thor.
          </p>

          <div className="thor-field">
            <label htmlFor="email">E-mail corporativo</label>
            <input
              autoComplete="email"
              id="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </div>

          <div className="thor-field">
            <label htmlFor="password">Senha</label>
            <input
              autoComplete="current-password"
              id="password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </div>

          {error ? (
            <p
              style={{
                fontSize: 12,
                color: "var(--danger)",
                marginBottom: 14,
                fontStyle: "italic",
                fontFamily: "Fraunces, serif"
              }}
            >
              {error}
            </p>
          ) : null}

          <button
            className="thor-btn"
            disabled={busy}
            style={{ width: "100%", padding: "13px", fontSize: 14 }}
            type="submit"
          >
            {busy ? "Entrando…" : "Entrar no painel"}
          </button>

          <div
            style={{
              marginTop: 28,
              borderTop: "1px solid var(--hairline)",
              paddingTop: 14,
              display: "flex",
              justifyContent: "space-between",
              fontSize: 10.5,
              textTransform: "uppercase",
              letterSpacing: "0.12em",
              color: "var(--ink-mute)"
            }}
          >
            <span>v 2.4.0 · ambiente prod</span>
            <span>SSO Microsoft · em breve</span>
          </div>
        </form>
      </div>

      <div
        className="foot-italic"
        style={{
          marginTop: 18,
          display: "flex",
          gap: 24,
          justifyContent: "space-between",
          width: "100%",
          maxWidth: 28 * 16,
          borderTop: "1px solid var(--hairline)",
          paddingTop: 10
        }}
      >
        <span>001 / 247</span>
        <span>i. Entrada</span>
      </div>
    </main>
  );
}

function PrivateApp() {
  const [authenticated, setAuthenticated] = useState(hasToken());
  const [me, setMe] = useState<AgentMe | null>(null);
  const [view, setView] = useState<"kanban" | "accesses" | "admin" | "reports">("kanban");
  const [columns, setColumns] = useState<KanbanColumn[]>([]);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [ticketPanelOpen, setTicketPanelOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const isAdmin = me?.role === "administrador";

  async function load() {
    if (!authenticated || me?.must_change_password) return;
    setLoading(true);
    try {
      const data = await getKanban();
      setColumns(data);
      const tickets = data.flatMap((column) => column.tickets);
      setSelected((current) => {
        if (current && tickets.some((ticket) => ticket.id === current.id)) {
          return current;
        }
        return tickets[0] ?? null;
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (authenticated) {
      getMe()
        .then((agent) => {
          setMe(agent);
          if (agent.must_change_password) {
            setColumns([]);
            setSelected(null);
          }
        })
        .catch(console.error);
    } else {
      setMe(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated]);

  useEffect(() => {
    if (authenticated && me && !me.must_change_password) {
      load().catch(console.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated, me?.id, me?.must_change_password]);

  useEffect(() => {
    const handleExpired = () => setAuthenticated(false);
    window.addEventListener("auth:expired", handleExpired);
    return () => window.removeEventListener("auth:expired", handleExpired);
  }, []);

  if (!authenticated) {
    return <Login onLogged={() => setAuthenticated(true)} />;
  }

  if (me?.must_change_password) {
    return (
      <PasswordResetGate
        me={me}
        onChanged={(agent) => {
          setMe(agent);
        }}
      />
    );
  }

  return (
    <main className="min-h-screen" style={{ background: "var(--bg)" }}>
      <header className="thor-app-header">
        <div className="thor-app-brand">
          <img
            alt="THOR Consultoria"
            className="thor-app-logo"
            src="/assets/logo-thor-1.png"
          />
          <div
            className="font-display"
            style={{
              fontStyle: "italic",
              color: "var(--ink-mute)",
              fontSize: 12,
              borderLeft: "1px solid var(--hairline-strong)",
              paddingLeft: 10
            }}
          >
            Suporte WinThor — TOTVS
          </div>
        </div>

        <nav className="thor-app-nav">
          <button
            className="font-display"
            onClick={() => setView("kanban")}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: "8px 14px",
              fontSize: 14,
              color: view === "kanban" ? "var(--ink)" : "var(--ink-soft)",
              borderBottom:
                view === "kanban"
                  ? "1px solid var(--accent)"
                  : "1px solid transparent",
              transition: "color .2s, border-color .2s",
              fontStyle: view === "kanban" ? "normal" : "normal"
            }}
            type="button"
          >
            Atendimento
          </button>
          {isAdmin && (
            <button
              className="font-display"
              onClick={() => setView("admin")}
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: "8px 14px",
                fontSize: 14,
                color: view === "admin" ? "var(--ink)" : "var(--ink-soft)",
                borderBottom:
                  view === "admin"
                    ? "1px solid var(--accent)"
                    : "1px solid transparent",
                transition: "color .2s, border-color .2s"
              }}
              type="button"
            >
              Cadastros
            </button>
          )}
          <button
            className="font-display"
            onClick={() => setView("accesses")}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: "8px 14px",
              fontSize: 14,
              color: view === "accesses" ? "var(--ink)" : "var(--ink-soft)",
              borderBottom:
                view === "accesses"
                  ? "1px solid var(--accent)"
                  : "1px solid transparent",
              transition: "color .2s, border-color .2s",
              display: "inline-flex",
              alignItems: "center",
              gap: 6
            }}
            type="button"
          >
            <KeyRound size={14} />
            Acessos
          </button>
          <button
            className="font-display"
            onClick={() => setView("reports")}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: "8px 14px",
              fontSize: 14,
              color: view === "reports" ? "var(--ink)" : "var(--ink-soft)",
              borderBottom:
                view === "reports"
                  ? "1px solid var(--accent)"
                  : "1px solid transparent",
              transition: "color .2s, border-color .2s",
              display: "inline-flex",
              alignItems: "center",
              gap: 6
            }}
            type="button"
          >
            <FileBarChart size={14} />
            Relatórios
          </button>
        </nav>

        <div className="thor-app-actions">
          <ThemeToggle />
          <button
            className="thor-icon-btn"
            onClick={() => setChangingPassword(true)}
            title="Alterar senha"
            type="button"
          >
            <KeyRound size={16} />
          </button>
          <button
            className="thor-icon-btn"
            disabled={loading}
            onClick={load}
            title="Atualizar"
            type="button"
          >
            <RefreshCcw className={loading ? "animate-spin" : ""} size={16} />
          </button>
          <button
            className="thor-icon-btn"
            onClick={() => {
              logout();
              setAuthenticated(false);
            }}
            title="Sair"
            type="button"
          >
            <LogOut size={16} />
          </button>
          <div className="thor-avatar" title={me?.name ?? "Conta"}>
            {initialsOf(me?.name)}
          </div>
        </div>
      </header>

      {changingPassword && me ? (
        <PasswordChangeModal
          onCancel={() => setChangingPassword(false)}
          onChanged={(agent) => {
            setMe(agent);
            setChangingPassword(false);
          }}
        />
      ) : null}

      {view === "kanban" ? (
        <div className={`thor-kanban-workspace ${ticketPanelOpen && selected ? "detail-open" : ""}`}>
          <section className="thor-kanban-panel">
            <KanbanBoard
              columns={columns}
              onSelect={(ticket) => {
                setSelected(ticket);
                setTicketPanelOpen(true);
              }}
              selectedId={selected?.id}
            />
          </section>
          <div
            aria-hidden={!ticketPanelOpen}
            className="thor-ticket-backdrop"
            onClick={() => setTicketPanelOpen(false)}
          />
          {selected ? (
            <div className="thor-ticket-shell">
              <TicketDrawer
                onChanged={load}
                onClose={() => setTicketPanelOpen(false)}
                ticket={selected}
                viewer={me}
              />
            </div>
          ) : null}
        </div>
      ) : view === "accesses" ? (
        <AccessVaultPanel />
      ) : view === "reports" ? (
        <ReportsPanel />
      ) : isAdmin ? (
        <AdminPanel />
      ) : (
        <AccessVaultPanel />
      )}
    </main>
  );
}

function PasswordResetGate({
  me,
  onChanged
}: {
  me: AgentMe;
  onChanged: (agent: AgentMe) => void;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password.length < 6) {
      setError("A nova senha deve ter pelo menos 6 caracteres.");
      return;
    }
    if (password !== confirmPassword) {
      setError("A confirmação da senha não confere.");
      return;
    }
    setBusy(true);
    try {
      onChanged(await changeOwnPassword(currentPassword, password));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao redefinir senha.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      className="grid min-h-screen place-items-center px-4 py-10"
      style={{ background: "var(--bg)" }}
    >
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <div
        className="w-full max-w-md border thor-stagger"
        style={{
          borderColor: "var(--hairline)",
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-md)"
        }}
      >
        <div className="px-10 pt-12 pb-2 text-center">
          <div
            className="font-display"
            style={{
              fontSize: "40px",
              fontWeight: 500,
              lineHeight: 1,
              letterSpacing: "-0.025em"
            }}
          >
            Nova senha
          </div>
          <div className="smallcaps" style={{ marginTop: 10 }}>
            Primeiro acesso de {me.name}
          </div>
        </div>

        <div className="divider-asterisk" style={{ margin: "20px 0 8px" }}>
          * &nbsp; * &nbsp; *
        </div>

        <form className="px-10 pb-10" onSubmit={handleSubmit}>
          <p
            style={{
              color: "var(--ink-mute)",
              margin: "0 0 24px",
              fontSize: 13
            }}
          >
            Sua senha inicial precisa ser trocada antes de acessar o painel.
          </p>

          <div className="thor-field">
            <label htmlFor="current-password">Senha temporária atual</label>
            <input
              autoComplete="current-password"
              id="current-password"
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
              type="password"
              value={currentPassword}
            />
          </div>

          <div className="thor-field">
            <label htmlFor="new-password">Nova senha</label>
            <input
              autoComplete="new-password"
              id="new-password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </div>

          <div className="thor-field">
            <label htmlFor="confirm-password">Confirmar nova senha</label>
            <input
              autoComplete="new-password"
              id="confirm-password"
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              type="password"
              value={confirmPassword}
            />
          </div>

          {error ? (
            <p
              style={{
                fontSize: 12,
                color: "var(--danger)",
                marginBottom: 14,
                fontStyle: "italic",
                fontFamily: "Fraunces, serif"
              }}
            >
              {error}
            </p>
          ) : null}

          <button
            className="thor-btn"
            disabled={busy}
            style={{ width: "100%", padding: "13px", fontSize: 14 }}
            type="submit"
          >
            {busy ? "Salvando…" : "Salvar nova senha"}
          </button>
        </form>
      </div>
    </main>
  );
}

function PasswordChangeModal({
  onCancel,
  onChanged
}: {
  onCancel: () => void;
  onChanged: (agent: AgentMe) => void;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (newPassword.length < 6) {
      setError("A nova senha deve ter pelo menos 6 caracteres.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("A confirmação da senha não confere.");
      return;
    }
    setBusy(true);
    try {
      onChanged(await changeOwnPassword(currentPassword, newPassword));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao alterar senha.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.28)",
        display: "grid",
        placeItems: "center",
        padding: 24,
        zIndex: 50
      }}
    >
      <form
        className="w-full max-w-md border thor-stagger"
        onSubmit={handleSubmit}
        style={{
          borderColor: "var(--hairline)",
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-md)",
          padding: 24
        }}
      >
        <h2
          className="font-display"
          style={{ margin: "0 0 6px", fontSize: 24, fontWeight: 500 }}
        >
          Alterar senha
        </h2>
        <p style={{ color: "var(--ink-mute)", margin: "0 0 18px", fontSize: 13 }}>
          Informe sua senha atual para definir uma nova senha de acesso.
        </p>

        <div className="thor-field">
          <label htmlFor="modal-current-password">Senha atual</label>
          <input
            autoComplete="current-password"
            id="modal-current-password"
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
            type="password"
            value={currentPassword}
          />
        </div>

        <div className="thor-field">
          <label htmlFor="modal-new-password">Nova senha</label>
          <input
            autoComplete="new-password"
            id="modal-new-password"
            onChange={(event) => setNewPassword(event.target.value)}
            required
            type="password"
            value={newPassword}
          />
        </div>

        <div className="thor-field">
          <label htmlFor="modal-confirm-password">Confirmar nova senha</label>
          <input
            autoComplete="new-password"
            id="modal-confirm-password"
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
            type="password"
            value={confirmPassword}
          />
        </div>

        {error ? (
          <p
            style={{
              fontSize: 12,
              color: "var(--danger)",
              marginBottom: 14,
              fontStyle: "italic",
              fontFamily: "Fraunces, serif"
            }}
          >
            {error}
          </p>
        ) : null}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 18 }}>
          <button className="thor-btn secondary" onClick={onCancel} type="button">
            Cancelar
          </button>
          <button className="thor-btn" disabled={busy} type="submit">
            {busy ? "Salvando…" : "Salvar senha"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default function App() {
  const publicTicketMatch = window.location.pathname.match(/^\/t\/([^/]+)$/);
  if (publicTicketMatch) {
    return <PublicTicketPage token={decodeURIComponent(publicTicketMatch[1])} />;
  }

  return <PrivateApp />;
}
