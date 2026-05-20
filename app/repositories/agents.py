from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.support import Agent


class AgentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, agent_id: int) -> Agent | None:
        return self.db.get(Agent, agent_id)

    def get_by_email(self, email: str) -> Agent | None:
        return self.db.scalar(select(Agent).where(Agent.email == email))
