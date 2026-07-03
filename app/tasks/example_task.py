import logging

from celery_app.celery import celery

logger = logging.getLogger(__name__)

@celery.task(name='example_task')
def example_task(message: str):
    """Simple task that logs the received message.
    """
    logger.info(f"Executed example_task with message: {message}")
    return f"Processed: {message}"
