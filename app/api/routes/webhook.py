from fastapi import APIRouter, status

from app.fsm.models import WebhookResponse, WhatsAppWebhook

router = APIRouter()


@router.post(
    "/whatsapp", status_code=status.HTTP_200_OK, response_model=WebhookResponse
)
def webhook(payload: WhatsAppWebhook) -> WebhookResponse:
    # TODO: Add payload to background processing
    print(payload)
    return WebhookResponse()
