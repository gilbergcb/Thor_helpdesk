from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

MEDIA_KEYS: tuple[tuple[str, str, str], ...] = (
    ("image", "image", "imageUrl"),
    ("audio", "audio", "audioUrl"),
    ("video", "video", "videoUrl"),
    ("document", "document", "documentUrl"),
    ("sticker", "sticker", "stickerUrl"),
)


class ZApiWebhookPayload(BaseModel):
    message_id: str | None = Field(default=None, validation_alias=AliasChoices("messageId", "id"))
    group_id: str | None = Field(default=None, validation_alias=AliasChoices("chatId", "groupId"))
    phone: str | None = Field(default=None)
    sender_phone: str | None = Field(
        default=None, validation_alias=AliasChoices("senderPhone", "sender", "from")
    )
    sender_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("senderName", "pushName"),
    )
    participant_phone: str | None = Field(default=None, validation_alias="participantPhone")
    participant_name: str | None = Field(default=None, validation_alias="participantName")
    from_me: bool | None = Field(default=None, validation_alias="fromMe")
    text: str | dict[str, Any] | None = None
    message: str | None = None
    is_group: bool | None = Field(default=None, validation_alias="isGroup")
    media_type: str | None = None
    media_url: str | None = None
    media_mime_type: str | None = None
    caption: str | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def flatten_common_payloads(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        text = out.get("text")
        if isinstance(text, dict) and isinstance(text.get("message"), str):
            out["message"] = text["message"]
        for key, mtype, url_field in MEDIA_KEYS:
            block = out.get(key)
            if isinstance(block, dict):
                url = block.get(url_field) or block.get("url")
                if url:
                    out.setdefault("media_type", mtype)
                    out.setdefault("media_url", url)
                    out.setdefault(
                        "media_mime_type",
                        block.get("mimeType") or block.get("mimetype"),
                    )
                    caption = block.get("caption") or block.get("fileName")
                    if caption:
                        out.setdefault("caption", caption)
                    break
        return out

    @property
    def normalized_group_id(self) -> str | None:
        return self.group_id or self.phone

    @property
    def normalized_sender_phone(self) -> str | None:
        return self.sender_phone or self.participant_phone or self.phone

    @property
    def normalized_sender_name(self) -> str | None:
        return self.sender_name or self.participant_name

    @property
    def normalized_content(self) -> str:
        if isinstance(self.text, str) and self.text.strip():
            return self.text
        if isinstance(self.message, str) and self.message.strip():
            return self.message
        if self.caption:
            return self.caption
        return ""

    @property
    def has_payload(self) -> bool:
        return bool(self.normalized_content) or bool(self.media_url)


class WebhookResult(BaseModel):
    ignored: bool = False
    ticket_id: int | None = None
    protocol: str | None = None
    reason: str | None = None
