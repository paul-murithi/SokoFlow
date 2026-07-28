from datetime import datetime
from enum import StrEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class QueueName(StrEnum):
    """
    Celery Worker Queue names
    """

    CONVERSATION = "conversation_tasks"
    REPORTS = "reports_tasks"
    NOTIFICATIONS = "notifications_tasks"
    MAINTENANCE = "maintenance_tasks"
    DEFAULT = "default_tasks"
    SCHEDULES = "schedules_tasks"


# FSM Redis Sessions
# TODO: Add more states later
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
