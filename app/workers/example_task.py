import logging

from celery_app.celery import celery

logger = logging.getLogger(__name__)


@celery.task
def sample_task(message: str) -> str:
    """Simple task that logs the received message."""
    logger.info(f"Executed example_task with message: {message}")
    return f"Processed: {message}"


@celery.task(name="heartbeat")
def heartbeat() -> None:
    logger.info("Heartbeat task executed")
