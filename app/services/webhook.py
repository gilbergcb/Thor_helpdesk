from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.enums import HistoryEventType, MessageDirection
from app.models.ticket import Ticket, TicketHistory, TicketMessage
from app.repositories.tickets import TicketRepository
from app.repositories.whatsapp import WhatsAppRepository
from app.schemas.webhook import WebhookResult, ZApiWebhookPayload
from app.services.media_storage import download_to_storage

TRIGGER = "#chamado"

MEDIA_PLACEHOLDER = {
    "image": "[imagem]",
    "audio": "[áudio]",
    "video": "[vídeo]",
    "document": "[documento]",
    "sticker": "[sticker]",
}


class WebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.whatsapp = WhatsAppRepository(db)
        self.tickets = TicketRepository(db)

    def process_message(self, payload: ZApiWebhookPayload) -> WebhookResult:
        group_external_id = payload.normalized_group_id
        sender_phone = payload.normalized_sender_phone
        content = payload.normalized_content.strip()
        media_url = payload.media_url
        media_type = payload.media_type

        if not group_external_id or not sender_phone or not (content or media_url):
            return WebhookResult(ignored=True, reason="missing group, sender or content")

        group = self.whatsapp.get_group_by_external_id(group_external_id)
        if group is None or not group.is_active:
            return WebhookResult(ignored=True, reason="unknown or inactive group")

        user = self.whatsapp.upsert_user(group, sender_phone, payload.normalized_sender_name)
        is_new_ticket = content.lower().startswith(TRIGGER)
        ticket = None

        if is_new_ticket:
            description = content[len(TRIGGER):].strip() or content
            title = description.splitlines()[0][:180] or "Chamado via WhatsApp"
            ticket = Ticket(
                protocol=self.tickets.next_protocol(),
                title=title,
                description=description,
                opened_at=datetime.now(UTC),
                client=group.client,
                whatsapp_group=group,
                requester=user,
            )
            self.db.add(ticket)
            self.db.flush()
            self.db.add(
                TicketHistory(
                    ticket=ticket,
                    event_type=HistoryEventType.ticket_created,
                    description=f"Ticket criado automaticamente pelo gatilho {TRIGGER}",
                )
            )
        else:
            ticket = self.tickets.latest_open_for_group(group.id)
            if ticket is None:
                self.db.commit()
                return WebhookResult(ignored=True, reason="message does not start a ticket")

        stored_content = content or MEDIA_PLACEHOLDER.get(media_type or "", "[mídia]")
        storage_key = (
            download_to_storage(media_url, payload.media_mime_type) if media_url else None
        )
        self.db.add(
            TicketMessage(
                ticket=ticket,
                direction=MessageDirection.inbound,
                content=stored_content,
                media_type=media_type,
                media_url=media_url,
                media_mime_type=payload.media_mime_type,
                media_storage_key=storage_key,
                external_message_id=payload.message_id,
                sender=user,
            )
        )
        self.db.add(
            TicketHistory(
                ticket=ticket,
                event_type=HistoryEventType.message_received,
                description=f"Mensagem recebida de {user.name or user.phone}",
            )
        )
        self.db.commit()
        self.db.refresh(ticket)
        return WebhookResult(ticket_id=ticket.id, protocol=ticket.protocol)
