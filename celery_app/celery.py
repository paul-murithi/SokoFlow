import os

from celery import Celery
from kombu import Queue

from app.utils.types import QueueName

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

celery = Celery(
    "sokoflow_celery",
    broker=broker_url,
    backend=backend_url,
    include=["app.workers"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=False,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_queue=QueueName.DEFAULT,
    task_queues=(
        Queue(QueueName.CONVERSATION),
        Queue(QueueName.REPORTS),
        Queue(QueueName.REPORTS),
        Queue(QueueName.MAINTENANCE),
        Queue(QueueName.DEFAULT),
    ),
    task_routes={
        "app.workers.conversation_tasks.*": {
            "queue": QueueName.CONVERSATION,
        },
        "app.workers.report_tasks.*": {
            "queue": QueueName.REPORTS,
        },
        "app.workers.notification_tasks.*": {
            "queue": QueueName.NOTIFICATIONS,
        },
        "app.workers.maintenance_tasks.*": {
            "queue": QueueName.MAINTENANCE,
        },
        "app.workers.example_tasks.*": {
            "queue": QueueName.DEFAULT,
        },
    },
)

# celery.conf.beat_schedule = {
#     "heartbeat-every-10-seconds": {
#         "task": "heartbeat",
#         "schedule": 10.0,
#     },
# }
# TODO: Risk of results piling up in the result_backend crashing redis
