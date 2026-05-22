import asyncio
import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.core.database import Base
from app.models import Agent, Client, Ticket, TicketHistory, TicketMessage, WhatsAppGroup
from app.models.enums import AgentRole, HistoryEventType, MessageDirection, TicketStatus
from app.services.tickets import TicketService


class FakeZApiClient:
    sent_messages: list[tuple[str, str]] = []

    async def send_group_message(self, group_id: str, message: str) -> dict[str, str]:
        self.sent_messages.append((group_id, message))
        return {"messageId": "fake-message-id"}


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def ticket_fixture(db: Session) -> tuple[Ticket, Agent]:
    client = Client(name="Cliente Teste", document="123")
    group = WhatsAppGroup(client=client, group_id="120363000000000000-group", name="Grupo Teste")
    agent = Agent(
        name="Supervisor THOR",
        email="supervisor@example.com",
        phone="5585999999999",
        password_hash="hash",
        role=AgentRole.supervisor,
    )
    ticket = Ticket(
        protocol="THOR-20260522-0001",
        title="Erro no pedido",
        description="Cliente reportou erro no pedido",
        opened_at=datetime.now(UTC),
        client=client,
        whatsapp_group=group,
    )
    db.add_all([client, group, agent, ticket])
    db.commit()
    db.refresh(ticket)
    db.refresh(agent)
    return ticket, agent


def test_change_status_to_closed_sends_group_notice(
    db: Session,
    ticket_fixture: tuple[Ticket, Agent],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket, agent = ticket_fixture
    FakeZApiClient.sent_messages = []
    monkeypatch.setattr("app.services.tickets.ZApiClient", FakeZApiClient)

    asyncio.run(TicketService(db).change_status(ticket.id, TicketStatus.fechado, agent))

    assert FakeZApiClient.sent_messages == [
        (
            "120363000000000000-group",
            (
                "O chamado THOR-20260522-0001 foi fechado por "
                "Supervisor THOR (5585999999999).\n\n"
                "Obrigado pelo retorno. Se precisar de novo atendimento, abra um novo chamado."
            ),
        )
    ]

    saved_message = db.scalar(
        select(TicketMessage).where(TicketMessage.external_message_id == "fake-message-id")
    )
    assert saved_message is not None
    assert saved_message.direction == MessageDirection.outbound
    assert "foi fechado" in saved_message.content

    saved_history = db.scalar(
        select(TicketHistory).where(
            TicketHistory.event_type == HistoryEventType.message_sent,
            TicketHistory.description == "Aviso de fechamento enviado ao grupo via Z-API",
        )
    )
    assert saved_history is not None


def test_change_status_does_not_repeat_closed_notice_for_same_status(
    db: Session,
    ticket_fixture: tuple[Ticket, Agent],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket, agent = ticket_fixture
    ticket.status = TicketStatus.fechado
    db.commit()
    FakeZApiClient.sent_messages = []
    monkeypatch.setattr("app.services.tickets.ZApiClient", FakeZApiClient)

    asyncio.run(TicketService(db).change_status(ticket.id, TicketStatus.fechado, agent))

    assert FakeZApiClient.sent_messages == []
