from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import AgentRole


class AdminAuditLogRead(BaseModel):
    """F-18: row do admin_audit_log."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_agent_id: int | None
    actor_email: str | None
    actor_role: str | None
    action: str
    target_type: str
    target_id: str | None
    payload_hash: str | None
    source_ip: str | None
    created_at: datetime


class ClientCreate(BaseModel):
    name: str
    document: str | None = None
    cnpj: str | None = None
    is_active: bool = True


class ClientRead(ClientCreate):
    id: int

    model_config = {"from_attributes": True}


class WhatsAppGroupCreate(BaseModel):
    client_id: int
    group_id: str
    name: str
    is_active: bool = True


class WhatsAppGroupRead(WhatsAppGroupCreate):
    id: int
    client: ClientRead

    model_config = {"from_attributes": True}


class EmployeeRoleCreate(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True


class EmployeeRoleRead(EmployeeRoleCreate):
    id: int

    model_config = {"from_attributes": True}


class ClientEmployeeCreate(BaseModel):
    whatsapp_group_id: int
    role_id: int | None = None
    name: str
    phone: str
    email: str | None = None
    notes: str | None = None
    is_active: bool = True


class ClientEmployeeRead(ClientEmployeeCreate):
    id: int
    client: ClientRead
    whatsapp_group: WhatsAppGroupRead
    role: EmployeeRoleRead | None = None

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str
    role: AgentRole = AgentRole.atendente
    is_active: bool = True


class AgentRead(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str | None = None
    role: AgentRole
    is_active: bool
    must_change_password: bool
    totp_enabled: bool

    model_config = {"from_attributes": True}


class ClientUpdate(BaseModel):
    name: str | None = None
    document: str | None = None
    cnpj: str | None = None
    is_active: bool | None = None


class WhatsAppGroupUpdate(BaseModel):
    client_id: int | None = None
    group_id: str | None = None
    name: str | None = None
    is_active: bool | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    password: str | None = None
    role: AgentRole | None = None
    is_active: bool | None = None


class EmployeeRoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class ClientEmployeeUpdate(BaseModel):
    whatsapp_group_id: int | None = None
    role_id: int | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ClientAccessCredentialCreate(BaseModel):
    client_id: int
    title: str
    access_url: str | None = None
    username: str | None = None
    secret: str
    notes: str | None = None
    is_active: bool = True


class ClientAccessCredentialRead(BaseModel):
    id: int
    client_id: int
    title: str
    access_url: str | None
    username: str | None
    is_active: bool
    client: ClientRead

    model_config = {"from_attributes": True}


class ClientAccessCredentialCreated(ClientAccessCredentialRead):
    reveal_token: str | None = None


class ClientAccessCredentialRevealRequest(BaseModel):
    totp_code: str


class ClientAccessCredentialReveal(BaseModel):
    id: int
    title: str
    access_url: str | None
    username: str | None
    secret: str
    notes: str | None = None
