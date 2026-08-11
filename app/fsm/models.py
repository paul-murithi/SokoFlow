from datetime import datetime
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SessionState(StrEnum):
    # Record Product Flow
    IDLE = "IDLE"
    START_ADD_PRODUCT = "START_ADD_PRODUCT"
    ADD_PRODUCT_NAME = "ADD_PRODUCT_NAME"
    ADD_PRODUCT_PRICE = "ADD_PRODUCT_PRICE"
    ADD_PRODUCT_QTY = "ADD_PRODUCT_QTY"
    CONFIRM_ADD_PRODUCT = "CONFIRM_ADD_PRODUCT"

    # Record Sale Flow
    RECORD_SALE_PRODUCT = "RECORD_SALE_PRODUCT"
    RECORD_SALE_PRODUCT_SELECTION = "RECORD_SALE_PRODUCT_SELECTION"  # Awaiting user option
    RECORD_SALE_QTY = "RECORD_SALE_QTY"
    CONFIRM_SALE = "CONFIRM_SALE"

    # Check Stock flow
    CHECK_STOCK_PRODUCT = "CHECK_STOCK_PRODUCT"
    CHECK_STOCK_PRODUCT_SELECTION = "CHECK_STOCK_PRODUCT_SELECTION"


class ScoredProductMatch(BaseModel):
    """Pairs a product with its fuzzy match score to evaluate thresholds."""

    id: UUID
    shop_id: UUID
    name: str
    sku: str
    price: Decimal
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class ProductResolutionStatus(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    EXACT_MATCH = "EXACT_MATCH"
    AMBIGUOUS = "AMBIGUOUS"


class ProductResolution(BaseModel):
    status: ProductResolutionStatus
    product: ScoredProductMatch | None = None
    candidates: list[ScoredProductMatch] = []


class SessionContext(BaseModel):
    shop_id: Optional[UUID] = None
    product_id: Optional[UUID] = None
    product_name: Optional[str] = None
    product_price: Optional[Decimal] = None
    product_qty: Optional[int] = None
    flow_started_at: Optional[datetime] = None
    history: List[SessionState] = Field(default_factory=list)
    error_count: int = 0
    last_activity: Optional[datetime] = None
    product_candidates: list[ScoredProductMatch] = []


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


class Intent(StrEnum):
    UNKNOWN = "UNKNOWN"
    ADD_PRODUCT = "ADD_PRODUCT"
    RECORD_SALE = "RECORD_SALE"


class InboundMessagePayload(BaseModel):
    sender: str
    message_text: str
    message_id: str

    @classmethod
    def from_whatsapp_webhook(cls, webhook: WhatsAppWebhook) -> "InboundMessagePayload | None":
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
