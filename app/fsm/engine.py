from datetime import datetime, timezone
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.fsm.fsm_utils import (
    parse_confirmation,
    parse_price,
    parse_product_name,
    parse_quantity,
)
from app.fsm.intent_resolver import IntentResolver
from app.fsm.models import FSMResult, SessionContext, SessionState, UserSession
from app.schemas.product import ProductCreate
from app.services.product_service import ProductService
from app.utils.errors import InvalidInputError

from .models import Intent

OVERRIDE_COMMANDS = frozenset({"cancel", "menu", "exit", "stop"})


class FSMEngine:
    MAX_ERROR_ATTEMPTS = settings.max_fsm_errors

    def __init__(self, db_session: AsyncSession | None = None) -> None:
        # Optional DB session for confirm-step persistence.
        self.db = db_session
        self.product_service = ProductService()
        self.intent_resolver = IntentResolver()
        self._handler_map: dict[
            SessionState, Callable[[UserSession, str], Awaitable[FSMResult]]
        ] = {
            SessionState.IDLE: self._handle_idle,
            SessionState.START_ADD_PRODUCT: self._handle_idle,
            SessionState.ADD_PRODUCT_NAME: self._handle_add_product_name,
            SessionState.ADD_PRODUCT_PRICE: self._handle_add_product_price,
            SessionState.ADD_PRODUCT_QTY: self._handle_add_product_qty,
            SessionState.CONFIRM_ADD_PRODUCT: self._handle_confirm_add,
        }

    async def process_message(
        self, session: UserSession, message_text: str
    ) -> FSMResult:
        """Processes an incoming message against the current session state."""
        previous_state = session.state
        normalized_text = message_text.strip().lower()

        if normalized_text in OVERRIDE_COMMANDS:
            self._transition(session, SessionState.IDLE)
            self._clear_context_preserving_history(session)
            return self._build_result(
                previous_state=previous_state,
                session=session,
                reply_text="Flow cancelled. How can I help you today?",
            )

        handler = self._handler_map.get(session.state, self._handle_idle)

        try:
            result = await handler(session, message_text)
            session.context.error_count = 0
            return result
        except InvalidInputError as exc:
            session.context.error_count += 1

            if session.context.error_count >= self.MAX_ERROR_ATTEMPTS:
                self._transition(session, SessionState.IDLE)
                self._clear_context_preserving_history(session)
                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    reply_text=(
                        "Too many invalid attempts. I've cancelled this request "
                        "so we can start fresh. Type 'add product' to try again."
                    ),
                )

            return self._build_result(
                previous_state=previous_state,
                session=session,
                reply_text=exc.message,
            )

    async def _handle_idle(self, session: UserSession, message_text: str) -> FSMResult:
        previous_state = session.state
        intent = self.intent_resolver.resolve(message_text)

        if intent is Intent.UNKNOWN:
            raise InvalidInputError("Type 'add product' to begin.")

        if intent is Intent.RECORD_SALE:
            raise InvalidInputError(
                "Sales flow is not available yet. Type 'add product' to begin."
            )

        session.context.flow_started_at = datetime.now(timezone.utc)
        self._transition(session, SessionState.ADD_PRODUCT_NAME)

        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text="Great, let's add a product. What is the product name?",
        )

    async def _handle_add_product_name(
        self, session: UserSession, message_text: str
    ) -> FSMResult:
        previous_state = session.state

        session.context.product_name = parse_product_name(message_text)
        self._transition(session, SessionState.ADD_PRODUCT_PRICE)

        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text="Nice. What is the price in KES?",
        )

    async def _handle_add_product_price(
        self, session: UserSession, message_text: str
    ) -> FSMResult:
        previous_state = session.state

        session.context.product_price = parse_price(message_text)
        self._transition(session, SessionState.ADD_PRODUCT_QTY)

        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text="Got it. How many units are in stock?",
        )

    async def _handle_add_product_qty(
        self, session: UserSession, message_text: str
    ) -> FSMResult:
        previous_state = session.state
        product_name = session.context.product_name
        product_price = session.context.product_price

        if product_name is None or product_price is None:
            raise InvalidInputError(
                "I lost some product details. Type 'add product' to start again."
            )

        session.context.product_qty = parse_quantity(message_text)
        self._transition(session, SessionState.CONFIRM_ADD_PRODUCT)

        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text=(
                f"Please confirm: {product_name} at KES {product_price:.2f}, "
                f"quantity {session.context.product_qty}. Reply Yes or No."
            ),
        )

    async def _handle_confirm_add(
        self, session: UserSession, message_text: str
    ) -> FSMResult:
        previous_state = session.state

        is_confirmed = parse_confirmation(message_text)
        if not is_confirmed:
            self._transition(session, SessionState.IDLE)
            self._clear_context_preserving_history(session)
            return self._build_result(
                previous_state=previous_state,
                session=session,
                reply_text="No problem. I cancelled the product flow.",
            )

        product_name = session.context.product_name
        product_price = session.context.product_price
        product_qty = session.context.product_qty

        if product_name is None or product_price is None or product_qty is None:
            raise InvalidInputError(
                "I lost some product details. Type 'add product' to start again."
            )

        await self._persist_product_db(session)

        self._transition(session, SessionState.IDLE)
        self._clear_context_preserving_history(session)
        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text=(
                f"Product added: {product_name} at KES {product_price:.2f} "
                f"with opening quantity {product_qty}."
            ),
        )

    async def _persist_product_db(self, session: UserSession) -> None:
        if self.db is None:
            return

        shop_id = session.context.shop_id
        product_name = session.context.product_name
        product_price = session.context.product_price

        if shop_id is None or product_name is None or product_price is None:
            return

        payload = ProductCreate(name=product_name, price=product_price, shop_id=shop_id)
        # TODO: Database save may fail
        await self.product_service.create_product(payload, self.db)

    def _transition(self, session: UserSession, new_state: SessionState) -> None:
        if session.state != new_state:
            session.context.history.append(session.state)
            session.state = new_state
        session.context.last_activity = datetime.now(timezone.utc)

    def _clear_context_preserving_history(self, session: UserSession) -> None:
        history = list(session.context.history)
        session.context = SessionContext(
            shop_id=session.context.shop_id,
            history=history,
            last_activity=datetime.now(timezone.utc),
        )

    def _build_result(
        self,
        *,
        previous_state: SessionState,
        session: UserSession,
        reply_text: str,
    ) -> FSMResult:
        return FSMResult(
            previous_state=previous_state,
            new_state=session.state,
            context=session.context.model_copy(deep=True),
            reply_text=reply_text,
        )
