import {
  Activity,
  ArrowRight,
  Building2,
  Clock3,
  Gauge,
  Headphones,
  ListChecks,
  RefreshCcw,
  ShieldCheck,
  TrendingUp,
  Users
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

import { getAttendanceReport } from "../services/api";
import type { AgentMe, AttendanceReport, KanbanColumn, Ticket, TicketStatus } from "../types/api";

type AppView = "home" | "kanban" | "accesses" | "admin" | "reports";

type Props = {
  columns: KanbanColumn[];
  loading: boolean;
  me: AgentMe | null;
  onNavigate: (view: AppView) => void;
  onOpenTicket: (ticket: Ticket) => void;
  onRefresh: () => void;
};

const statusLabels: Record<TicketStatus, string> = {
  novo: "novo",
  triagem: "triagem",
  em_atendimento: "em atendimento",
  aguardando_cliente: "aguardando cliente",
  resolvido: "resolvido",
  fechado: "fechado"
};

const openStatuses = new Set<TicketStatus>([
  "novo",
  "triagem",
  "em_atendimento",
  "aguardando_cliente"
]);

const priorityWeight = {
  critica: 4,
  alta: 3,
  media: 2,
  baixa: 1
};

function dateOnly(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultDateFrom(): string {
  const value = new Date();
  value.setDate(value.getDate() - 30);
  return dateOnly(value);
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function ageInHours(value: string): number {
  return Math.max(0, (Date.now() - new Date(value).getTime()) / 36e5);
}

function formatAge(value: string): string {
  const hours = ageInHours(value);
  if (hours < 1) return "agora";
  if (hours < 24) return `${Math.floor(hours)}h`;
  return `${Math.floor(hours / 24)}d`;
}

function formatHours(value: number | null | undefined): string {
  if (value == null) return "-";
  if (value < 1) return `${Math.round(value * 60)}min`;
  return `${value.toFixed(1).replace(".", ",")}h`;
}

function personName(ticket: Ticket): string {
  return ticket.requester?.name ?? ticket.requester?.phone ?? "solicitante não identificado";
}

function buildInsight(openTotal: number, unassigned: number, waiting: number, hotTickets: number) {
  if (unassigned > 0) {
    return `${unassigned} chamado${unassigned > 1 ? "s" : ""} sem atendente puxando a fila.`;
  }
  if (hotTickets > 0) {
    return `${hotTickets} chamado${hotTickets > 1 ? "s" : ""} de alta prioridade merece vitrine hoje.`;
  }
  if (waiting > 0) {
    return `${waiting} atendimento${waiting > 1 ? "s" : ""} aguardando retorno do cliente.`;
  }
  if (openTotal === 0) return "Fila limpa. Bom momento para revisar indicadores.";
  return "Operação sob controle, com a fila distribuída.";
}

function topGroups<T>(
  rows: T[],
  keyOf: (row: T) => string,
  totalOf?: (row: T) => number
): Array<{ name: string; total: number }> {
  const map = new Map<string, number>();
  rows.forEach((row) => {
    const key = keyOf(row);
    if (!key) return;
    map.set(key, (map.get(key) ?? 0) + (totalOf?.(row) ?? 1));
  });
  return [...map.entries()]
    .map(([name, total]) => ({ name, total }))
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name))
    .slice(0, 4);
}

export function HomeDashboard({
  columns,
  loading,
  me,
  onNavigate,
  onOpenTicket,
  onRefresh
}: Props) {
  const [report, setReport] = useState<AttendanceReport | null>(null);
  const [reportError, setReportError] = useState("");
  const [reportLoading, setReportLoading] = useState(false);

  const tickets = useMemo(() => columns.flatMap((column) => column.tickets), [columns]);
  const openTickets = useMemo(
    () => tickets.filter((ticket) => openStatuses.has(ticket.status)),
    [tickets]
  );

  const waiting = tickets.filter((ticket) => ticket.status === "aguardando_cliente").length;
  const unassigned = openTickets.filter((ticket) => !ticket.assigned_agent).length;
  const mine = openTickets.filter((ticket) => ticket.assigned_agent?.id === me?.id).length;
  const hotTickets = openTickets.filter(
    (ticket) => ticket.priority === "alta" || ticket.priority === "critica"
  ).length;
  const oldestTicket = [...openTickets].sort(
    (a, b) => new Date(a.opened_at).getTime() - new Date(b.opened_at).getTime()
  )[0];

  const queue = useMemo(
    () =>
      [...openTickets]
        .sort((a, b) => {
          const priorityDiff = priorityWeight[b.priority] - priorityWeight[a.priority];
          if (priorityDiff !== 0) return priorityDiff;
          return new Date(a.opened_at).getTime() - new Date(b.opened_at).getTime();
        })
        .slice(0, 7),
    [openTickets]
  );

  const reportRows = report?.tickets ?? [];
  const companyLeaders = topGroups(reportRows, (row) => row.client_name);
  const agentLeaders = topGroups(reportRows, (row) => row.agent_name ?? "Sem atendente");
  const statusEntries = Object.entries(report?.summary.by_status ?? {})
    .map(([status, total]) => ({ status: status as TicketStatus, total }))
    .sort((a, b) => b.total - a.total);
  const maxStatus = Math.max(1, ...statusEntries.map((entry) => entry.total));
  const resolvedRate = report?.summary.total
    ? Math.round(((report.summary.resolved_total + report.summary.closed_total) / report.summary.total) * 100)
    : 0;
  const insight = buildInsight(openTickets.length, unassigned, waiting, hotTickets);

  useEffect(() => {
    setReportLoading(true);
    setReportError("");
    getAttendanceReport({
      date_from: defaultDateFrom(),
      date_to: dateOnly(new Date())
    })
      .then(setReport)
      .catch((err) => setReportError(err instanceof Error ? err.message : "Erro ao carregar indicadores."))
      .finally(() => setReportLoading(false));
  }, []);

  return (
    <section className="thor-home-page thor-stagger">
      <div className="thor-home-hero">
        <div>
          <span className="smallcaps">Central THOR</span>
          <h1 className="font-display">Pulso dos atendimentos</h1>
          <p>{insight}</p>
        </div>
        <div className="thor-home-hero-actions">
          <button className="thor-btn ghost" disabled={loading} onClick={onRefresh} type="button">
            <RefreshCcw className={loading ? "animate-spin" : ""} size={15} />
            Atualizar
          </button>
          <button className="thor-btn" onClick={() => onNavigate("kanban")} type="button">
            Abrir Kanban
            <ArrowRight size={15} />
          </button>
        </div>
      </div>

      <div className="thor-home-metrics">
        <MetricCard icon={<Activity size={18} />} label="Fila aberta" note="agora" value={openTickets.length} />
        <MetricCard icon={<Headphones size={18} />} label="Meus atendimentos" note={me?.name ?? "conta"} value={mine} />
        <MetricCard icon={<Clock3 size={18} />} label="Mais antigo" note={oldestTicket?.protocol ?? "sem pendência"} value={oldestTicket ? formatAge(oldestTicket.opened_at) : "0"} />
        <MetricCard icon={<ShieldCheck size={18} />} label="Resolução 30d" note={`${report?.summary.total ?? 0} no período`} value={`${resolvedRate}%`} />
      </div>

      <div className="thor-home-layout">
        <section className="thor-home-panel thor-home-queue">
          <PanelHead
            action="Atendimento"
            icon={<ListChecks size={16} />}
            onAction={() => onNavigate("kanban")}
            title="Fila viva"
          />
          <div className="thor-home-ticket-list">
            {queue.length ? (
              queue.map((ticket) => (
                <button
                  className="thor-home-ticket"
                  key={ticket.id}
                  onClick={() => onOpenTicket(ticket)}
                  type="button"
                >
                  <span className={`thor-tag ${ticket.status}`}>
                    <span className="dot" />
                    {statusLabels[ticket.status]}
                  </span>
                  <strong>{ticket.title}</strong>
                  <span>{ticket.client.name} · {personName(ticket)}</span>
                  <small>
                    {ticket.protocol} · {formatDateTime(ticket.opened_at)} · {formatAge(ticket.opened_at)}
                  </small>
                </button>
              ))
            ) : (
              <div className="thor-home-empty">Nenhum atendimento aberto.</div>
            )}
          </div>
        </section>

        <section className="thor-home-panel">
          <PanelHead
            action="Relatórios"
            icon={<Gauge size={16} />}
            onAction={() => onNavigate("reports")}
            title="Painel 30 dias"
          />
          <div className="thor-home-status-list">
            {statusEntries.length ? (
              statusEntries.map((entry) => (
                <div className="thor-home-status-row" key={entry.status}>
                  <div>
                    <span className={`thor-tag ${entry.status}`}>
                      <span className="dot" />
                      {statusLabels[entry.status] ?? entry.status}
                    </span>
                    <strong className="tnum">{entry.total}</strong>
                  </div>
                  <span style={{ "--bar": `${(entry.total / maxStatus) * 100}%` } as CSSProperties} />
                </div>
              ))
            ) : (
              <div className="thor-home-empty">
                {reportLoading ? "Carregando indicadores..." : reportError || "Sem dados no período."}
              </div>
            )}
          </div>
          <div className="thor-home-resolution">
            <span className="smallcaps">Tempo médio</span>
            <strong className="font-display tnum">
              {formatHours(report?.summary.avg_resolution_hours)}
            </strong>
          </div>
        </section>

        <section className="thor-home-panel">
          <PanelHead icon={<Building2 size={16} />} title="Empresas em foco" />
          <RankList empty="Sem empresas no período." rows={companyLeaders} />
        </section>

        <section className="thor-home-panel">
          <PanelHead icon={<Users size={16} />} title="Atendentes em movimento" />
          <RankList empty="Sem atendentes no período." rows={agentLeaders} />
        </section>

        <section className="thor-home-panel thor-home-radar">
          <PanelHead icon={<TrendingUp size={16} />} title="Radar" />
          <div className="thor-home-radar-grid">
            <RadarItem label="Sem atendente" tone={unassigned > 0 ? "danger" : "ok"} value={unassigned} />
            <RadarItem label="Aguardando cliente" tone={waiting > 0 ? "warn" : "ok"} value={waiting} />
            <RadarItem label="Alta prioridade" tone={hotTickets > 0 ? "danger" : "ok"} value={hotTickets} />
          </div>
        </section>
      </div>
    </section>
  );
}

function MetricCard({
  icon,
  label,
  note,
  value
}: {
  icon: ReactNode;
  label: string;
  note: string;
  value: string | number;
}) {
  return (
    <div className="thor-card thor-home-metric">
      <div>
        <span>{icon}</span>
        <small className="smallcaps">{label}</small>
      </div>
      <strong className="font-display tnum">{value}</strong>
      <em>{note}</em>
    </div>
  );
}

function PanelHead({
  action,
  icon,
  onAction,
  title
}: {
  action?: string;
  icon: ReactNode;
  onAction?: () => void;
  title: string;
}) {
  return (
    <header className="thor-home-panel-head">
      <div>
        {icon}
        <h2 className="font-display">{title}</h2>
      </div>
      {action && onAction ? (
        <button className="thor-btn-ghost" onClick={onAction} type="button">
          {action}
          <ArrowRight size={14} />
        </button>
      ) : null}
    </header>
  );
}

function RankList({ empty, rows }: { empty: string; rows: Array<{ name: string; total: number }> }) {
  if (!rows.length) return <div className="thor-home-empty">{empty}</div>;
  const max = Math.max(1, ...rows.map((row) => row.total));
  return (
    <div className="thor-home-rank-list">
      {rows.map((row, index) => (
        <div className="thor-home-rank-row" key={row.name}>
          <span className="font-display tnum">{String(index + 1).padStart(2, "0")}</span>
          <strong>{row.name}</strong>
          <em className="tnum">{row.total}</em>
          <i style={{ "--bar": `${(row.total / max) * 100}%` } as CSSProperties} />
        </div>
      ))}
    </div>
  );
}

function RadarItem({ label, tone, value }: { label: string; tone: "danger" | "ok" | "warn"; value: number }) {
  return (
    <div className={`thor-home-radar-item ${tone}`}>
      <span className="smallcaps">{label}</span>
      <strong className="font-display tnum">{value}</strong>
    </div>
  );
}
