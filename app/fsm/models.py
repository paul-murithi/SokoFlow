from datetime import datetime
from enum import IntEnum, StrEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class SessionState(StrEnum):
    IDLE = "IDLE"
    START_ADD_PRODUCT = "START_ADD_PRODUCT"
    ADD_PRODUCT_NAME = "ADD_PRODUCT_NAME"
    ADD_PRODUCT_PRICE = "ADD_PRODUCT_PRICE"
    ADD_PRODUCT_QTY = "ADD_PRODUCT_QTY"
    SALE = "SALE"
    WAIT_PRODUCT = "RECORD_SALE_PRODUCT"
    WAIT_QTY = "RECORD_SALE_QTY"
    CONFIRM = "CONFIRM_SALE"
    DONE = "DONE"


class SessionContext(BaseModel):
    product_name: Optional[str] = None
    flow_started_at: Optional[datetime] = None
    history: List[SessionState] = Field(default_factory=list)
    error_count: int = 0
    last_activity: Optional[datetime] = None


class UserSession(BaseModel):
    phone: str
    state: SessionState
    context: SessionContext


class UpdateSessionResult(IntEnum):
    SUCCESS = 1
    STATE_MISMATCH = 0
    CORRUPTED_DATA = -1


"""
WhatsApp Message
"""


class Text(BaseModel):
    body: str


class Message(BaseModel):
    from_: str = Field(alias="from")
    id: str
    type: str
    text: Text


class Value(BaseModel):
    messages: list[Message]


class Change(BaseModel):
    value: Value


class Entry(BaseModel):
    changes: list[Change]


class WhatsAppWebhook(BaseModel):
    object: str
    entry: list[Entry]


class WebhookResponse(BaseModel):
    status: str = Field(default="success")
    message: str = Field(default="accepted")


class InboundMessagePayload(BaseModel):
    sender: str
    message_text: str
    message_id: str

    @classmethod
    def from_whatsapp_webhook(
        cls, webhook: WhatsAppWebhook
    ) -> "InboundMessagePayload | None":
        """Transforms a raw Meta webhook into a flat internal contract."""
        try:
            message = webhook.entry[0].changes[0].value.messages[0]
            return cls(
                sender=message.from_,
                message_text=message.text.body if message.text else "",
                message_id=message.id,
            )
        except (IndexError, AttributeError, TypeError):
            # TODO: Handle non-message payloads (like status webhooks)
            # TODO: logging
            return None


class FSMResult(BaseModel):
    """The immutable outcome of an FSM state transition computation."""

    previous_state: SessionState
    new_state: SessionState
    context: SessionContext
    reply_text: str
