import asyncio
import logging

from app.fsm.conversation_store import ConversationStore, get_conversation_store
from app.fsm.engine import FSMEngine
from app.fsm.models import InboundMessagePayload, SessionContext, SessionState, UserSession
from celery_app.celery import celery

from .message_sender import MessageDeliveryError, build_message_sender

logger = logging.getLogger(__name__)
MESSAGE_SENDER = build_message_sender()

# Minimal state management for the simulator.
# TODO: Replace with FSM state management
_SESSION_STATE: dict[str, str] = {}
_PENDING_PRODUCT_NAME: dict[str, str] = {}


def build_reply(inbound_message: InboundMessagePayload) -> str:
    sender = inbound_message.sender
    message_text = inbound_message.message_text.strip()
    normalized_text = message_text.lower()
    current_state = _SESSION_STATE.get(sender, "IDLE")

    if current_state == "IDLE":
        if normalized_text == "add product":
            _SESSION_STATE[sender] = "WAIT_PRODUCT_NAME"
            return "Product name?"

        return "Type 'add product' to start."

    if current_state == "WAIT_PRODUCT_NAME":
        _PENDING_PRODUCT_NAME[sender] = message_text
        _SESSION_STATE[sender] = "WAIT_PRODUCT_PRICE"
        return "Price?"

    if current_state == "WAIT_PRODUCT_PRICE":
        product_name = _PENDING_PRODUCT_NAME.pop(sender, "Unknown product")
        _SESSION_STATE[sender] = "IDLE"
        return f"Saved: {product_name} at {message_text}"

    _SESSION_STATE[sender] = "IDLE"
    return "Type 'add product' to start."


@celery.task
def conversation_task(payload: dict[str, object]) -> str:
    return asyncio.run(conversation(payload))

async def conversation(payload: dict[str, object]) -> str:
    # Reconstruct flat payload
    store = get_conversation_store()
    inbound_message = InboundMessagePayload.model_validate(payload)
    phone_number = inbound_message.sender

    # Fetch or Initialize session
    old_session= await store.get_session(phone_number)
    if old_session is None:
        current_session = UserSession(
            phone=phone_number,
            state=SessionState.IDLE,
            context=SessionContext()
        )
    else:
        current_session = old_session.model_copy(deep=True)

    print(current_session)
    # TODO: Process inside FSM
    fsm_engine = FSMEngine() # pyright: ignore[]

    reply_text = build_reply(inbound_message)

    try:
        MESSAGE_SENDER.send_text(inbound_message.sender, reply_text)
    except MessageDeliveryError:
        logger.exception("Failed to deliver reply")

    return reply_text
