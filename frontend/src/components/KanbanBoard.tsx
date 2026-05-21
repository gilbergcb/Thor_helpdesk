import type { KanbanColumn, Ticket } from "../types/api";
import { TicketCard } from "./TicketCard";

type Props = {
  columns: KanbanColumn[];
  selectedId?: number;
  onSelect: (ticket: Ticket) => void;
};

const labels: Record<string, string> = {
  novo: "Novo",
  triagem: "Triagem",
  em_atendimento: "Em atendimento",
  aguardando_cliente: "Aguardando cliente",
  resolvido: "Resolvido",
  fechado: "Fechado"
};

function pad2(n: number) {
  return n < 10 ? `0${n}` : String(n);
}

export function KanbanBoard({ columns, selectedId, onSelect }: Props) {
  return (
    <div
      className="thor-kanban-board thor-stagger"
      style={{
        gridAutoFlow: "column",
        gridAutoColumns: "minmax(260px, 1fr)"
      }}
    >
      {columns.map((column) => (
        <section className="flex min-w-[280px] flex-col" key={column.status}>
          <header
            className="grid items-center gap-3"
            style={{
              gridTemplateColumns: "minmax(0, 1fr) 34px",
              padding: "0 4px 10px",
              borderBottom: "1px solid var(--hairline)",
              marginBottom: 12
            }}
          >
            <span
              style={{
                fontFamily: "Geist, sans-serif",
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                color: "var(--ink)",
                fontWeight: 500,
                minWidth: 0,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis"
              }}
              title={labels[column.status] ?? column.status}
            >
              {labels[column.status] ?? column.status}
            </span>
            <span
              className="font-display"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 34,
                height: 24,
                border: "1px solid var(--hairline)",
                borderRadius: 999,
                background: "rgba(255, 255, 255, 0.54)",
                fontStyle: "italic",
                fontSize: 12,
                color: "var(--ink-mute)",
                fontVariantNumeric: "tabular-nums",
                justifySelf: "end"
              }}
            >
              {pad2(column.tickets.length)}
            </span>
          </header>
          <div className="flex flex-col gap-3">
            {column.tickets.map((ticket) => (
              <TicketCard
                key={ticket.id}
                onSelect={onSelect}
                selected={selectedId === ticket.id}
                ticket={ticket}
              />
            ))}
            {column.tickets.length === 0 ? (
              <div
                className="foot-italic"
                style={{
                  border: "1px dashed var(--hairline)",
                  padding: "14px 12px",
                  textAlign: "center",
                  minHeight: 48
                }}
              >
                — vazio —
              </div>
            ) : null}
          </div>
        </section>
      ))}
    </div>
  );
}
