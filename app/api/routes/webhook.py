from fastapi import APIRouter, status

from app.fsm.models import (
    InboundMessagePayload,
    WebhookResponse,
    WhatsAppWebhook,
)
from app.workers.conversation_tasks import conversation_task
from app.workers.queues import QueueName

router = APIRouter()


@router.post(
    "/whatsapp", status_code=status.HTTP_200_OK, response_model=WebhookResponse
)
def webhook(request_payload: WhatsAppWebhook) -> WebhookResponse:
    payload = InboundMessagePayload.from_whatsapp_webhook(request_payload)

    if not payload:
        return WebhookResponse(status="ignored", message="Not a text message event")

    conversation_task.apply_async(
        args=(payload.model_dump(),), queue=QueueName.CONVERSATION
    )
    return WebhookResponse()
