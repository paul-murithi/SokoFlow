import logging
from typing import Any

from app.utils.idempotency import idempotent_task
from celery_app.celery import celery

logger = logging.getLogger(__name__)


@celery.task(autoretry_for=(Exception,), max_retries=5, retry_backoff=True)
@idempotent_task()
def send_low_stock_alert(payload: dict[str, Any]) -> None:
    """Celery task to send low stock alert with idempotency protection."""
    logger.info("Executing send_low_stock_alert with payload: %s", payload)
    return None
