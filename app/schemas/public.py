from datetime import datetime

from pydantic import BaseModel, computed_field

from app.models.enums import MessageDirection, TicketStatus


class PublicAgentRead(BaseModel):
    name: str
    phone: str | None = None

    model_config = {"from_attributes": True}


class PublicTicketMessageRead(BaseModel):
    id: int
    direction: MessageDirection
    content: str
    media_type: str | None = None
    media_storage_key: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def local_media_url(self) -> str | None:
        if not self.media_storage_key:
            return None
        return f"/api/v1/media/{self.id}"


class PublicTicketRead(BaseModel):
    protocol: str
    title: str
    status: TicketStatus
    client_name: str
    group_name: str
    requester_name: str | None = None
    assigned_agent: PublicAgentRead | None = None
    messages: list[PublicTicketMessageRead] = []


class PublicTicketMessageCreate(BaseModel):
    message: str
