import os

from celery import Celery


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

# TODO: Risk of results piling up in the result_backend crashing redis