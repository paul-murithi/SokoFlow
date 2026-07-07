from enum import StrEnum

class QueueName(StrEnum):
    WEBHOOK = "webhook"
    REPORTS = "reports"
    NOTIFICATIONS = "notifications"
    MAINTENANCE = "maintenance"
    DEFAULT = "default"