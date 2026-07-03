import os

from celery import Celery
from celery.schedules import crontab


broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
backend_url = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')

celery = Celery(
    'sokoflow_celery',
    broker=broker_url,
    backend=backend_url,
    include=['app.tasks']
    )

celery.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    task_acks_late=False,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True
)

# celery.conf.beat_schedule = {
#     "heartbeat-every-10-seconds": {
#         "task": "heartbeat",
#         "schedule": 10.0,
#     },
# }
# TODO: Risk of results piling up in the result_backend crashing redis