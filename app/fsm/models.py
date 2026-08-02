from datetime import datetime
from enum import IntEnum, StrEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class SessionState(StrEnum):
    IDLE = "IDLE"
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
