from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import TicketPriority, TicketStatus


class ReportOption(BaseModel):
    id: int
    name: str


class AttendanceReportOptions(BaseModel):
    clients: list[ReportOption]
    employees: list[ReportOption]
    agents: list[ReportOption]


class AttendanceReportSummary(BaseModel):
    total: int
    open_total: int
    resolved_total: int
    closed_total: int
    avg_resolution_hours: float | None = None
    by_status: dict[str, int]


class AttendanceReportRow(BaseModel):
    id: int
    protocol: str
    title: str
    status: TicketStatus
    priority: TicketPriority
    opened_at: datetime
    closed_at: datetime | None
    resolution_hours: float | None = None
    client_id: int
    client_name: str
    employee_id: int | None = None
    employee_name: str | None = None
    requester_name: str | None = None
    requester_phone: str | None = None
    agent_id: int | None = None
    agent_name: str | None = None


class AttendanceReport(BaseModel):
    date_from: date
    date_to: date
    summary: AttendanceReportSummary
    tickets: list[AttendanceReportRow]
