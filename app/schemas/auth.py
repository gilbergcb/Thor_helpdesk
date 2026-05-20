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
    role: AgentRole
    must_change_password: bool

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
