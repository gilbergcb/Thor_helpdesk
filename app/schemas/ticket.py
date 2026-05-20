from datetime import datetime

from pydantic import BaseModel, computed_field

from app.models.enums import MessageDirection, TicketPriority, TicketStatus


class ClientRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class WhatsAppGroupRead(BaseModel):
    id: int
    group_id: str
    name: str

    model_config = {"from_attributes": True}


class AgentRead(BaseModel):
    id: int
    name: str
    email: str

    model_config = {"from_attributes": True}


class EmployeeRoleRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class RequesterRead(BaseModel):
    id: int
    phone: str
    name: str | None = None
    employee_id: int | None = None
    employee_role: EmployeeRoleRead | None = None

    model_config = {"from_attributes": True}


class TicketMessageRead(BaseModel):
    id: int
    direction: MessageDirection
    content: str
    media_type: str | None = None
    media_url: str | None = None
    media_mime_type: str | None = None
    media_storage_key: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def local_media_url(self) -> str | None:
        if not self.media_storage_key:
            return None
        return f"/api/v1/media/{self.id}"


class PendingTicketMessageRead(BaseModel):
    id: int
    content: str
    media_type: str | None = None
    media_url: str | None = None
    media_mime_type: str | None = None
    media_storage_key: str | None = None
    reason: str | None = None
    created_at: datetime
    sender: RequesterRead | None = None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def local_media_url(self) -> str | None:
        if not self.media_storage_key:
            return None
        return f"/api/v1/media/pending/{self.id}"


class TicketRead(BaseModel):
    id: int
    protocol: str
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    opened_at: datetime
    client: ClientRead
    whatsapp_group: WhatsAppGroupRead
    requester: RequesterRead | None = None
    assigned_agent: AgentRead | None = None

    model_config = {"from_attributes": True}


class TicketDetail(TicketRead):
    messages: list[TicketMessageRead] = []
    pending_messages: list[PendingTicketMessageRead] = []


class AssignTicketRequest(BaseModel):
    agent_id: int | None = None


class UpdateTicketStatusRequest(BaseModel):
    status: TicketStatus


class ReplyTicketRequest(BaseModel):
    message: str


class TicketUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: TicketPriority | None = None
    category_id: int | None = None


class CreateTicketFromPendingRequest(BaseModel):
    title: str | None = None
    description: str | None = None


class KanbanColumn(BaseModel):
    status: TicketStatus
    tickets: list[TicketRead]
