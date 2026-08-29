import hmac
import logging
import time
from uuid import uuid4

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.redis import get_redis
from app.fsm.conversation_store import ConversationStore
from app.fsm.models import (
    InboundMessagePayload,
    WebhookResponse,
    WhatsAppWebhook,
)
from app.workers.conversation_tasks import conversation_task
from app.workers.queues import QueueName

logger = logging.getLogger(__name__)
router = APIRouter()


def verify_hmac_signature(
    payload: bytes, signature_header: str | None, app_secret: str | None
) -> bool:
    if not signature_header or not app_secret:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_sig = signature_header[7:].strip()
    computed_sig = hmac.new(
        app_secret.encode("utf-8"),
        payload,
        "sha256",
    ).hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)


@router.post("/whatsapp", status_code=status.HTTP_200_OK, response_model=WebhookResponse)
async def webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> WebhookResponse | JSONResponse:
    start_time = time.perf_counter()

    raw_body = await request.body()

    if not verify_hmac_signature(raw_body, x_hub_signature_256, settings.whatsapp_app_secret):
        logger.warning("Invalid or missing HMAC signature on webhook request")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or missing HMAC signature"},
        )

    try:
        request_payload = WhatsAppWebhook.model_validate_json(raw_body)
    except Exception as exc:
        logger.warning("Malformed webhook payload: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Malformed webhook payload"},
        )

    correlation_id = request.headers.get(settings.correlation_id_header) or str(uuid4())

    payload = InboundMessagePayload.from_whatsapp_webhook(
        request_payload, correlation_id=correlation_id
    )
    if not payload:
        logger.warning("Webhook payload missing message event structure")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Missing required message fields in payload"},
        )

    try:
        redis = get_redis()
        store = ConversationStore(redis)

        is_duplicate = await store.is_duplicate(
            payload.message_id,
            ttl=settings.dedup_ttl_seconds,
        )

        if is_duplicate:
            logger.info("Duplicate webhook message_id %s ignored", payload.message_id)
            return WebhookResponse(status="ignored", message="Duplicate message ignored")

    except Exception as exc:
        logger.error("Redis deduplication error: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Infrastructure error during deduplication"},
        )

    try:
        conversation_task.apply_async(
            args=(payload.model_dump(),),
            queue=QueueName.CONVERSATION,
        )
    except Exception as exc:
        logger.error("Celery dispatch error: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Infrastructure error during task dispatch"},
        )

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Webhook processed in %.2fms [correlation_id=%s]",
        elapsed_ms,
        correlation_id,
    )

    return WebhookResponse()
