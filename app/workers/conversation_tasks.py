from app.fsm.models import InboundMessagePayload
from celery_app.celery import celery


@celery.task
def conversation_task(payload: InboundMessagePayload) -> str:
    return f"processed: {payload}"
