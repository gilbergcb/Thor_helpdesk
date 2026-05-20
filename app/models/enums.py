from enum import StrEnum


class TicketStatus(StrEnum):
    novo = "novo"
    triagem = "triagem"
    em_atendimento = "em_atendimento"
    aguardando_cliente = "aguardando_cliente"
    resolvido = "resolvido"
    fechado = "fechado"


class TicketPriority(StrEnum):
    baixa = "baixa"
    media = "media"
    alta = "alta"
    critica = "critica"


class MessageDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class AgentRole(StrEnum):
    atendente = "atendente"
    supervisor = "supervisor"
    administrador = "administrador"


class HistoryEventType(StrEnum):
    ticket_created = "ticket_created"
    ticket_assigned = "ticket_assigned"
    message_received = "message_received"
    message_sent = "message_sent"
    status_changed = "status_changed"
