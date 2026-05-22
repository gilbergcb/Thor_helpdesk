import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.core.database import Base
from app.models import (
    Agent,
    Client,
    PendingTicketMessage,
    Ticket,
    TicketHistory,
    TicketMessage,
    TicketPublicLink,
    WhatsAppGroup,
    WhatsAppUser,
)
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
    requester = WhatsAppUser(
        group=group,
        phone="55 (85) 8888-8888",
        name="Cliente Solicitante",
    )
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
        requester=requester,
    )
    db.add_all([client, group, requester, agent, ticket])
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
                "@558588888888 O chamado THOR-20260522-0001 foi fechado por "
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


def test_change_status_to_resolved_mentions_ticket_requester(
    db: Session,
    ticket_fixture: tuple[Ticket, Agent],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket, agent = ticket_fixture
    FakeZApiClient.sent_messages = []
    monkeypatch.setattr("app.services.tickets.ZApiClient", FakeZApiClient)

    asyncio.run(TicketService(db).change_status(ticket.id, TicketStatus.resolvido, agent))

    assert FakeZApiClient.sent_messages == [
        (
            "120363000000000000-group",
            (
                "@558588888888 O chamado THOR-20260522-0001 foi marcado como resolvido por "
                "Supervisor THOR (5585999999999).\n\n"
                "Se precisar de algo mais, responda por aqui."
            ),
        )
    ]


def test_change_status_to_waiting_customer_sends_active_public_link(
    db: Session,
    ticket_fixture: tuple[Ticket, Agent],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket, agent = ticket_fixture
    FakeZApiClient.sent_messages = []
    monkeypatch.setattr("app.services.tickets.ZApiClient", FakeZApiClient)
    monkeypatch.setattr(
        "app.services.public_links.generate_public_ticket_token",
        lambda: "public-token-123",
    )

    asyncio.run(
        TicketService(db).change_status(ticket.id, TicketStatus.aguardando_cliente, agent)
    )

    assert FakeZApiClient.sent_messages == [
        (
            "120363000000000000-group",
            (
                "@558588888888 O chamado THOR-20260522-0001 está aguardando seu retorno.\n\n"
                "Acesse o link abaixo para visualizar o atendimento e responder pelo portal:\n"
                "https://helpdesk.thorconsultoria.com.br/t/public-token-123\n\n"
                "O link fica ativo até a finalização do chamado."
            ),
        )
    ]
    public_link_count = db.query(TicketPublicLink).filter_by(ticket_id=ticket.id).count()
    assert public_link_count == 1

    saved_history = db.scalar(
        select(TicketHistory).where(
            TicketHistory.event_type == HistoryEventType.message_sent,
            TicketHistory.description == "Aviso de aguardando cliente enviado ao grupo via Z-API",
        )
    )
    assert saved_history is not None


def test_ticket_detail_only_shows_pending_messages_after_ticket_opened_at(
    db: Session,
    ticket_fixture: tuple[Ticket, Agent],
) -> None:
    ticket, _agent = ticket_fixture
    sender = WhatsAppUser(
        group=ticket.whatsapp_group,
        phone="5585888888888",
        name="Cliente",
    )
    older_pending = PendingTicketMessage(
        whatsapp_group=ticket.whatsapp_group,
        sender=sender,
        status="pending",
        content="Mensagem antes da abertura",
        created_at=ticket.opened_at - timedelta(minutes=30),
    )
    newer_pending = PendingTicketMessage(
        whatsapp_group=ticket.whatsapp_group,
        sender=sender,
        status="pending",
        content="Mensagem depois da abertura",
        created_at=ticket.opened_at + timedelta(minutes=5),
    )
    db.add_all([sender, older_pending, newer_pending])
    db.commit()

    detail = TicketService(db).get_detail(ticket.id)

    assert detail is not None
    assert [pending.content for pending in detail.pending_messages] == [
        "Mensagem depois da abertura"
    ]
