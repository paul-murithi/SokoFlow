import os
from typing import Any

from celery import Celery
from celery.signals import worker_process_init
from kombu import Queue

from app.core.redis import redis_client
from app.fsm.session_lua import register_session_update_script
from app.workers.async_runtime import initialize
from app.workers.queues import QueueName

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")


@worker_process_init.connect
def initialize_worker(**kwargs: Any) -> None:
    initialize()
    register_session_update_script(redis_client)


celery = Celery(
    "sokoflow_celery",
    broker=broker_url,
    backend=backend_url,
    include=[
        "app.workers.conversation_tasks",
        "app.workers.example_task",
        "app.workers.maintenance_tasks",
        "app.workers.notification_tasks",
        "app.workers.report_tasks",
    ],
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
        "app.workers.example_task.*": {
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
