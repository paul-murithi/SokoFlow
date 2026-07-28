from enum import StrEnum


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
