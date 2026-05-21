import { Download, FileBarChart, Filter } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { getAttendanceReport, getAttendanceReportOptions } from "../services/api";
import type { AttendanceReport, AttendanceReportOptions, AttendanceReportRow } from "../types/api";

const statusLabels: Record<string, string> = {
  novo: "novo",
  triagem: "triagem",
  em_atendimento: "em atendimento",
  aguardando_cliente: "aguardando cliente",
  resolvido: "resolvido",
  fechado: "fechado"
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

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("pt-BR");
}

function csvValue(value: string | number | null | undefined): string {
  const raw = value == null ? "" : String(value);
  return `"${raw.replace(/"/g, '""')}"`;
}

function buildCsv(rows: AttendanceReportRow[]): string {
  const header = [
    "Protocolo",
    "Abertura",
    "Fechamento",
    "Status",
    "Empresa",
    "Funcionario",
    "Telefone",
    "Atendente",
    "Prioridade",
    "Horas resolucao",
    "Titulo"
  ];
  const body = rows.map((row) => [
    row.protocol,
    formatDateTime(row.opened_at),
    formatDateTime(row.closed_at),
    statusLabels[row.status] ?? row.status,
    row.client_name,
    row.employee_name ?? row.requester_name ?? "",
    row.requester_phone ?? "",
    row.agent_name ?? "",
    row.priority,
    row.resolution_hours ?? "",
    row.title
  ]);
  return [header, ...body].map((line) => line.map(csvValue).join(";")).join("\n");
}

export function ReportsPanel() {
  const [options, setOptions] = useState<AttendanceReportOptions>({
    clients: [],
    employees: [],
    agents: []
  });
  const [report, setReport] = useState<AttendanceReport | null>(null);
  const [dateFrom, setDateFrom] = useState(defaultDateFrom);
  const [dateTo, setDateTo] = useState(() => dateOnly(new Date()));
  const [clientId, setClientId] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true);
    setError("");
    try {
      const data = await getAttendanceReport({
        date_from: dateFrom,
        date_to: dateTo,
        client_id: clientId,
        employee_id: employeeId,
        agent_id: agentId
      });
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar relatório.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    getAttendanceReportOptions()
      .then(setOptions)
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar filtros."));
    load().catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    load().catch(console.error);
  }

  function handleExport() {
    if (!report?.tickets.length) return;
    const blob = new Blob([buildCsv(report.tickets)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `relatorio-atendimentos-${report.date_from}-${report.date_to}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const summary = report?.summary;
  const rows = useMemo(() => report?.tickets ?? [], [report]);

  return (
    <section className="thor-admin-page px-8 py-6 thor-stagger">
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 24,
          borderBottom: "1px solid var(--hairline)",
          paddingBottom: 14,
          marginBottom: 24
        }}
      >
        <span className="font-display tnum" style={{ fontStyle: "italic", fontSize: 13, color: "var(--ink-mute)", minWidth: 56 }}>
          iv.
        </span>
        <h2 className="font-display" style={{ fontWeight: 500, fontSize: 26, margin: 0 }}>
          Relatórios
        </h2>
        <span className="foot-italic" style={{ marginLeft: "auto" }}>
          Atendimentos por período, empresa, funcionário e atendente
        </span>
      </div>

      <form className="thor-admin-form-panel" onSubmit={handleSubmit}>
        <div className="thor-admin-form-head">
          <span className="smallcaps">Filtros</span>
        </div>
        <div className="thor-admin-form-grid" style={{ gridTemplateColumns: "repeat(5, minmax(0, 1fr))" }}>
          <div className="thor-field">
            <label>De</label>
            <input onChange={(event) => setDateFrom(event.target.value)} type="date" value={dateFrom} />
          </div>
          <div className="thor-field">
            <label>Até</label>
            <input onChange={(event) => setDateTo(event.target.value)} type="date" value={dateTo} />
          </div>
          <div className="thor-field">
            <label>Empresa</label>
            <select onChange={(event) => setClientId(event.target.value)} value={clientId}>
              <option value="">Todas</option>
              {options.clients.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </div>
          <div className="thor-field">
            <label>Funcionário</label>
            <select onChange={(event) => setEmployeeId(event.target.value)} value={employeeId}>
              <option value="">Todos</option>
              {options.employees.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </div>
          <div className="thor-field">
            <label>Atendente</label>
            <select onChange={(event) => setAgentId(event.target.value)} value={agentId}>
              <option value="">Todos</option>
              {options.agents.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="thor-admin-form-footer">
          <span className="foot-italic">{error || `${rows.length} atendimentos encontrados`}</span>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="thor-btn secondary" disabled={busy} type="button" onClick={handleExport}>
              <Download size={15} /> CSV
            </button>
            <button className="thor-btn" disabled={busy} type="submit">
              <Filter size={15} /> Filtrar
            </button>
          </div>
        </div>
      </form>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 14,
          margin: "22px 0"
        }}
      >
        {[
          ["Total", summary?.total ?? 0],
          ["Em aberto", summary?.open_total ?? 0],
          ["Resolvidos", summary?.resolved_total ?? 0],
          ["Fechados", summary?.closed_total ?? 0]
        ].map(([label, value]) => (
          <div className="thor-card" key={label} style={{ padding: "16px 18px" }}>
            <div className="smallcaps">{label}</div>
            <div className="font-display tnum" style={{ fontSize: 28, marginTop: 6 }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      <div className="thor-data-table-shell" style={{ background: "var(--bg-elev)", border: "1px solid var(--hairline)" }}>
        <div className="thor-data-table-scroll">
          <table className="thor-table thor-admin-table">
            <thead>
              <tr>
                <th>Protocolo</th>
                <th>Empresa</th>
                <th>Funcionário</th>
                <th>Atendente</th>
                <th>Status</th>
                <th>Abertura</th>
                <th>Horas</th>
                <th>Título</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((row) => (
                <tr key={row.id}>
                  <td className="code">{row.protocol}</td>
                  <td>{row.client_name}</td>
                  <td>{row.employee_name ?? row.requester_name ?? row.requester_phone ?? "-"}</td>
                  <td>{row.agent_name ?? "-"}</td>
                  <td>
                    <span className={`thor-tag ${row.status}`}>
                      <span className="dot" />
                      {statusLabels[row.status] ?? row.status}
                    </span>
                  </td>
                  <td>{formatDateTime(row.opened_at)}</td>
                  <td className="tnum">{row.resolution_hours ?? "-"}</td>
                  <td>{row.title}</td>
                </tr>
              )) : (
                <tr>
                  <td className="foot-italic" colSpan={8} style={{ textAlign: "center", padding: "28px 16px" }}>
                    <FileBarChart size={16} /> Nenhum atendimento encontrado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
