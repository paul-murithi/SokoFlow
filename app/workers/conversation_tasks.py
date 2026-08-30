import logging

from app.core.config import settings
from app.core.database import get_worker_db
from app.fsm.conversation_store import get_conversation_store
from app.fsm.engine import FSMEngine
from app.fsm.models import (
    InboundMessagePayload,
    SessionContext,
    SessionState,
    UserSession,
)
from app.workers.async_runtime import run
from celery_app.celery import celery

from .message_sender import MessageDeliveryError, build_message_sender

logger = logging.getLogger(__name__)
MESSAGE_SENDER = build_message_sender()


@celery.task
def conversation_task(payload: dict[str, object]) -> str:
    return run(conversation(payload))


async def conversation(payload: dict[str, object]) -> str:
    store = get_conversation_store()
    inbound_message = InboundMessagePayload.model_validate(payload)
    phone_number = inbound_message.sender
    # correlation_id = inbound_message.correlation_id # pyright: ignore[]

    old_session = await store.get_session(phone_number)
    if old_session is None:
        current_session = UserSession(
            phone=phone_number,
            state=SessionState.IDLE,
            context=SessionContext(),
        )
    else:
        current_session = old_session.model_copy(deep=True)

    # Process Message
    async with get_worker_db() as db:
        fsm_engine = FSMEngine(db_session=db)
        result = await fsm_engine.process_message(current_session, inbound_message.message_text)

    # Save message to Session
    await store.save_session(
        session_id=phone_number,
        new_session=current_session,
        old_session=old_session,
        ttl=settings.session_ttl_seconds,
    )

    reply_text = result.reply_text

    try:
        MESSAGE_SENDER.send_text(inbound_message.sender, reply_text)
    except MessageDeliveryError:
        logger.exception("Failed to deliver reply")

    return reply_text
