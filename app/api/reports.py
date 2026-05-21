from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_agent
from app.core.database import get_db
from app.models.client import Client, ClientEmployee
from app.models.enums import AgentRole, TicketStatus
from app.models.support import Agent
from app.models.ticket import Ticket
from app.models.whatsapp import WhatsAppGroup, WhatsAppUser
from app.schemas.reports import (
    AttendanceReport,
    AttendanceReportOptions,
    AttendanceReportRow,
    AttendanceReportSummary,
    ReportOption,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _default_date_from() -> date:
    return datetime.now(UTC).date() - timedelta(days=30)


def _default_date_to() -> date:
    return datetime.now(UTC).date()


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _day_after(value: date) -> datetime:
    return datetime.combine(value + timedelta(days=1), time.min, tzinfo=UTC)


def _can_see_all(agent: Agent) -> bool:
    return agent.role in {AgentRole.supervisor, AgentRole.administrador}


def _apply_agent_scope(query, agent: Agent):
    if _can_see_all(agent):
        return query
    return query.where(Ticket.assigned_agent_id == agent.id)


@router.get("/attendance/options", response_model=AttendanceReportOptions)
def attendance_options(
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
) -> AttendanceReportOptions:
    if _can_see_all(agent):
        clients_query = select(Client).order_by(Client.name)
        employees_query = select(ClientEmployee).order_by(ClientEmployee.name)
    else:
        clients_query = (
            select(Client)
            .join(Ticket, Ticket.client_id == Client.id)
            .where(Ticket.assigned_agent_id == agent.id)
            .distinct()
            .order_by(Client.name)
        )
        employees_query = (
            select(ClientEmployee)
            .join(WhatsAppUser, WhatsAppUser.employee_id == ClientEmployee.id)
            .join(Ticket, Ticket.requester_id == WhatsAppUser.id)
            .where(Ticket.assigned_agent_id == agent.id)
            .distinct()
            .order_by(ClientEmployee.name)
        )
    clients = db.scalars(clients_query).all()
    employees = db.scalars(employees_query).all()
    agents_query = select(Agent).order_by(Agent.name)
    if not _can_see_all(agent):
        agents_query = agents_query.where(Agent.id == agent.id)
    agents = db.scalars(agents_query).all()
    return AttendanceReportOptions(
        clients=[ReportOption(id=item.id, name=item.name) for item in clients],
        employees=[ReportOption(id=item.id, name=item.name) for item in employees],
        agents=[ReportOption(id=item.id, name=item.name) for item in agents],
    )


@router.get("/attendance", response_model=AttendanceReport)
def attendance_report(
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[Agent, Depends(get_current_agent)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    client_id: int | None = None,
    employee_id: int | None = None,
    agent_id: int | None = None,
) -> AttendanceReport:
    date_from = date_from or _default_date_from()
    date_to = date_to or _default_date_to()
    if date_to < date_from:
        date_from, date_to = date_to, date_from

    query = (
        select(Ticket)
        .options(
            joinedload(Ticket.client),
            joinedload(Ticket.assigned_agent),
            joinedload(Ticket.requester).joinedload(WhatsAppUser.employee),
        )
        .join(Ticket.whatsapp_group)
        .outerjoin(Ticket.requester)
        .where(Ticket.opened_at >= _day_start(date_from))
        .where(Ticket.opened_at < _day_after(date_to))
        .order_by(Ticket.opened_at.desc(), Ticket.id.desc())
        .limit(1000)
    )
    query = _apply_agent_scope(query, agent)
    if client_id is not None:
        query = query.where(WhatsAppGroup.client_id == client_id)
    if employee_id is not None:
        query = query.where(WhatsAppUser.employee_id == employee_id)
    if agent_id is not None:
        query = query.where(Ticket.assigned_agent_id == agent_id)

    tickets = db.scalars(query).unique().all()
    rows = [_ticket_to_report_row(ticket) for ticket in tickets]
    by_status = {status.value: 0 for status in TicketStatus}
    for row in rows:
        by_status[row.status.value] += 1
    resolution_values = [
        row.resolution_hours
        for row in rows
        if row.resolution_hours is not None
        and row.status in {TicketStatus.resolvido, TicketStatus.fechado}
    ]
    avg_resolution_hours = (
        round(sum(resolution_values) / len(resolution_values), 2) if resolution_values else None
    )
    return AttendanceReport(
        date_from=date_from,
        date_to=date_to,
        summary=AttendanceReportSummary(
            total=len(rows),
            open_total=sum(
                by_status[key.value]
                for key in (
                    TicketStatus.novo,
                    TicketStatus.triagem,
                    TicketStatus.em_atendimento,
                    TicketStatus.aguardando_cliente,
                )
            ),
            resolved_total=by_status[TicketStatus.resolvido.value],
            closed_total=by_status[TicketStatus.fechado.value],
            avg_resolution_hours=avg_resolution_hours,
            by_status=by_status,
        ),
        tickets=rows,
    )


def _ticket_to_report_row(ticket: Ticket) -> AttendanceReportRow:
    requester = ticket.requester
    employee = requester.employee if requester else None
    agent = ticket.assigned_agent
    resolution_hours = None
    if ticket.closed_at:
        resolution_hours = round((ticket.closed_at - ticket.opened_at).total_seconds() / 3600, 2)
    return AttendanceReportRow(
        id=ticket.id,
        protocol=ticket.protocol,
        title=ticket.title,
        status=ticket.status,
        priority=ticket.priority,
        opened_at=ticket.opened_at,
        closed_at=ticket.closed_at,
        resolution_hours=resolution_hours,
        client_id=ticket.client_id,
        client_name=ticket.client.name,
        employee_id=employee.id if employee else None,
        employee_name=employee.name if employee else None,
        requester_name=requester.name if requester else None,
        requester_phone=requester.phone if requester else None,
        agent_id=agent.id if agent else None,
        agent_name=agent.name if agent else None,
    )
