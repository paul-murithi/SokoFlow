from datetime import date, datetime
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SessionState(StrEnum):
    # IDLE
    IDLE = "IDLE"

    # Record Product Flow
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

    # Daily Report Flow
    REPORT_PENDING = "REPORT_PENDING"


class MessageKey(StrEnum):
    FLOW_CANCELLED = "FLOW_CANCELLED"
    TOO_MANY_INVALID = "TOO_MANY_INVALID"
    UNKNOWN_INTENT = "UNKNOWN_INTENT"
    START_SALE = "START_SALE"
    START_STOCK_CHECK = "START_STOCK_CHECK"
    REPORT_GENERATING = "REPORT_GENERATING"
    START_ADD_PRODUCT = "START_ADD_PRODUCT"
    ASK_PRICE = "ASK_PRICE"
    ASK_STOCK_QUANTITY = "ASK_STOCK_QUANTITY"
    CONFIRM_PRODUCT = "CONFIRM_PRODUCT"
    PRODUCT_CANCELLED = "PRODUCT_CANCELLED"
    PRODUCT_ADDED = "PRODUCT_ADDED"
    ASK_SALE_QUANTITY = "ASK_SALE_QUANTITY"
    ASK_QUANTITY = "ASK_QUANTITY"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_CHOICES = "PRODUCT_CHOICES"
    CONFIRM_SALE = "CONFIRM_SALE"
    SALE_CANCELLED = "SALE_CANCELLED"
    SALE_RECORDED = "SALE_RECORDED"
    STOCK_NOT_FOUND = "STOCK_NOT_FOUND"
    STOCK_REMAINING = "STOCK_REMAINING"
    PRODUCT_NAME_INVALID = "PRODUCT_NAME_INVALID"
    PRICE_INVALID = "PRICE_INVALID"
    PRICE_NON_POSITIVE = "PRICE_NON_POSITIVE"
    QUANTITY_INVALID = "QUANTITY_INVALID"
    QUANTITY_NEGATIVE = "QUANTITY_NEGATIVE"
    CONFIRMATION_INVALID = "CONFIRMATION_INVALID"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INVALID_CHOICE = "INVALID_CHOICE"
    QUANTITY_TOO_LOW = "QUANTITY_TOO_LOW"
    SESSION_CONTEXT_LOST = "SESSION_CONTEXT_LOST"
    SHOP_NOT_FOUND = "SHOP_NOT_FOUND"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    LOW_STOCK_ALERT = "LOW_STOCK_ALERT"


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
    GENERATE_REPORT = "GENERATE_REPORT"
    CHECK_STOCK = "CHECK_STOCK"


class InboundMessagePayload(BaseModel):
    sender: str
    message_text: str
    message_id: str
    correlation_id: str | None = None

    @classmethod
    def from_whatsapp_webhook(
        cls, webhook: WhatsAppWebhook, correlation_id: str | None = None
    ) -> "InboundMessagePayload | None":
        """Transforms a raw Meta webhook into a flat internal contract."""
        try:
            message = webhook.entry[0].changes[0].value.messages[0]
            return cls(
                sender=message.from_,
                message_text=message.text.body if message.text else "",
                message_id=message.id,
                correlation_id=correlation_id,
            )
        except (IndexError, AttributeError, TypeError):
            # TODO: Handle non-message payloads (like status webhooks)
            # TODO: logging
            return None


class ReportPayload(BaseModel):
    shop_id: UUID
    recipient: str
    date_str: date | None = None


class FSMResult(BaseModel):
    """The immutable outcome of an FSM state transition computation."""

    previous_state: SessionState
    new_state: SessionState
    context: SessionContext
    message_key: MessageKey
    message_params: dict[str, object] = Field(default_factory=dict)

    @property
    def reply_text(self) -> str:
        """Render the default English text for legacy callers and existing tests."""
        from app.services.localization import render_message

        return render_message(MessageKey(self.message_key), "en", self.message_params)
