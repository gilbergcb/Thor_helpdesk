import logging
import re
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.enums import HistoryEventType, MessageDirection
from app.models.ticket import PendingTicketMessage, Ticket, TicketHistory, TicketMessage
from app.repositories.tickets import TicketRepository
from app.repositories.whatsapp import WhatsAppRepository
from app.schemas.webhook import WebhookResult, ZApiWebhookPayload
from app.services.media_storage import download_to_storage
from app.services.public_links import PublicTicketLinkService
from app.services.zapi import ZApiClient

TRIGGER = "#chamado"
TRIGGER_RE = re.compile(r"^\s*(?:#\s*chamado\b\s*[:\-–—]?\s*)+", re.IGNORECASE)
TICKET_REFERENCE_RE = re.compile(r"^#ticket\s+([A-Z0-9.-]+)\b", re.IGNORECASE)
logger = logging.getLogger(__name__)

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

    async def process_message(self, payload: ZApiWebhookPayload) -> WebhookResult:
        group_external_id = payload.normalized_group_id
        sender_phone = payload.normalized_sender_phone
        content = payload.normalized_content.strip()
        # F-19 Phase 5.4: media_url_for_storage descarta query string
        # (assinaturas/expirações Z-API) — é o que será persistido em
        # TicketMessage.media_url. O download usa raw_media_url (com query)
        # porque a query pode conter assinatura necessária para baixar.
        raw_media_url = payload.media_url
        media_url = raw_media_url.split("?")[0] if raw_media_url else None
        media_type = payload.media_type

        ticket_description = self._new_ticket_description(content)
        is_new_ticket = ticket_description is not None
        referenced_protocol = self._referenced_protocol(content)

        if payload.from_me and not (is_new_ticket or referenced_protocol):
            return WebhookResult(ignored=True, reason="outgoing message")
        if not group_external_id or not sender_phone or not (content or media_url):
            return WebhookResult(ignored=True, reason="missing group, sender or content")

        group = self.whatsapp.get_group_by_external_id(group_external_id)
        if group is None or not group.is_active:
            return WebhookResult(ignored=True, reason="unknown or inactive group")

        user = self.whatsapp.upsert_user(group, sender_phone, payload.normalized_sender_name)
        self.db.flush()
        ticket = None

        if is_new_ticket:
            description = ticket_description or "Chamado via WhatsApp"
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
            public_token = PublicTicketLinkService(self.db).create_for_ticket(ticket)
        elif referenced_protocol:
            ticket = self.tickets.get_by_protocol(referenced_protocol)
            if ticket is None or ticket.whatsapp_group_id != group.id:
                self._save_pending_message(
                    group.id,
                    user.id,
                    content,
                    raw_media_url,
                    media_url,
                    media_type,
                    payload,
                    "referência de ticket não encontrada ou pertence a outro grupo",
                )
                self.db.commit()
                return WebhookResult(ignored=True, reason="ticket reference not found")
        else:
            self._save_pending_message(
                group.id,
                user.id,
                content,
                raw_media_url,
                media_url,
                media_type,
                payload,
                f"mensagem sem {TRIGGER} e sem referência #ticket",
            )
            self.db.commit()
            return WebhookResult(ignored=True, reason="message pending triage")

        stored_content = content or MEDIA_PLACEHOLDER.get(media_type or "", "[mídia]")
        storage_key = (
            download_to_storage(raw_media_url, payload.media_mime_type) if raw_media_url else None
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
        if is_new_ticket:
            await self._send_open_confirmation(
                ticket,
                user.name or user.phone,
                description,
                public_token,
            )
        return WebhookResult(ticket_id=ticket.id, protocol=ticket.protocol)

    @staticmethod
    def _referenced_protocol(content: str) -> str | None:
        match = TICKET_REFERENCE_RE.match(content.strip())
        return match.group(1).upper() if match else None

    @staticmethod
    def _new_ticket_description(content: str) -> str | None:
        if not TRIGGER_RE.match(content):
            return None
        return TRIGGER_RE.sub("", content, count=1).strip()

    def _save_pending_message(
        self,
        group_id: int,
        sender_id: int,
        content: str,
        raw_media_url: str | None,
        media_url: str | None,
        media_type: str | None,
        payload: ZApiWebhookPayload,
        reason: str,
    ) -> None:
        stored_content = content or MEDIA_PLACEHOLDER.get(media_type or "", "[mídia]")
        storage_key = (
            download_to_storage(raw_media_url, payload.media_mime_type) if raw_media_url else None
        )
        self.db.add(
            PendingTicketMessage(
                whatsapp_group_id=group_id,
                sender_id=sender_id,
                content=stored_content,
                media_type=media_type,
                media_url=media_url,
                media_mime_type=payload.media_mime_type,
                media_storage_key=storage_key,
                external_message_id=payload.message_id,
                reason=reason,
            )
        )

    async def _send_open_confirmation(
        self,
        ticket: Ticket,
        requester: str,
        summary: str,
        public_token: str,
    ) -> None:
        public_url = PublicTicketLinkService(self.db).public_url(public_token)
        message = (
            "Chamado aberto com sucesso.\n\n"
            f"Protocolo: {ticket.protocol}\n"
            f"Solicitante: {requester}\n"
            f"Resumo: {summary[:600]}\n\n"
            "Acompanhe e interaja com o atendimento pelo link:\n"
            f"{public_url}\n\n"
            "O link fica ativo ate a finalizacao do chamado."
        )
        try:
            result = await ZApiClient().send_group_message(ticket.whatsapp_group.group_id, message)
        except Exception as exc:
            logger.warning(
                "Falha ao enviar confirmação automática do ticket %s: %s",
                ticket.id,
                exc,
            )
            return
        external_id = result.get("messageId") or result.get("id")
        self.db.add(
            TicketMessage(
                ticket=ticket,
                direction=MessageDirection.outbound,
                content=message,
                external_message_id=external_id,
            )
        )
        self.db.add(
            TicketHistory(
                ticket=ticket,
                event_type=HistoryEventType.message_sent,
                description="Confirmação automática enviada ao grupo via Z-API",
            )
        )
        self.db.commit()
