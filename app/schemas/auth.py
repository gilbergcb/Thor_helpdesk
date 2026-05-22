from pydantic import BaseModel, EmailStr

from app.models.enums import AgentRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AgentMe(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str | None = None
    role: AgentRole
    must_change_password: bool
    totp_enabled: bool

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TotpEnableRequest(BaseModel):
    code: str


class TotpDisableRequest(BaseModel):
    code: str
