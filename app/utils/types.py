from datetime import datetime
from enum import StrEnum
from typing import List

from pydantic import BaseModel


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
class SessionState(StrEnum):
    IDLE = "IDLE"
    SALE = "SALE"
    WAIT_PRODUCT = "RECORD_SALE_PRODUCT"
    WAIT_QTY = "RECORD_SALE_QTY"
    CONFIRM = "CONFIRM_SALE"
    DONE = "DONE"


class SessionContext(BaseModel):
    product_name: str
    flow_started_at: datetime
    history: List[SessionState]
    error_count: int
    last_activity: datetime


class UserSession(BaseModel):
    phone: str
    state: SessionState
    context: SessionContext
