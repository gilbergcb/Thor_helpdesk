from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.support import Agent
from app.repositories.agents import AgentRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.agents = AgentRepository(db)

    def authenticate(self, email: str, password: str) -> Agent | None:
        agent = self.agents.get_by_email(email)
        if not agent or not agent.is_active:
            return None
        if not verify_password(password, agent.password_hash):
            return None
        return agent

    def create_token(self, agent: Agent) -> str:
        return create_access_token(str(agent.id))

    def change_password(self, agent: Agent, current_password: str, new_password: str) -> Agent | None:
        if not verify_password(current_password, agent.password_hash):
            return None
        agent.password_hash = get_password_hash(new_password)
        agent.must_change_password = False
        self.db.commit()
        self.db.refresh(agent)
        return agent
