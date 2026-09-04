from datetime import datetime, timezone
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.fsm.flows import AddProductFlow, RecordSaleFlow, StockLookupFlow
from app.fsm.flows.generate_report import ReportFlow
from app.fsm.intent_resolver import IntentResolver
from app.fsm.models import FSMResult, Intent, SessionState, UserSession
from app.fsm.primitives import FSMPrimitives
from app.utils.errors import InvalidInputError

OVERRIDE_COMMANDS = frozenset({"cancel", "menu", "exit", "stop"})


class FSMEngine(FSMPrimitives):
    MAX_ERROR_ATTEMPTS = settings.max_fsm_errors

    def __init__(self, db_session: AsyncSession | None = None) -> None:
        self.db = db_session
        self.intent_resolver = IntentResolver()
        self.add_product_flow = AddProductFlow(db_session=db_session)
        self.record_sale_flow = RecordSaleFlow(db_session=db_session)
        self.stock_lookup_flow = StockLookupFlow(db_session=db_session)
        self.generate_report_flow = ReportFlow(db_session=db_session)
        self._handler_map: dict[
            SessionState, Callable[[UserSession, str], Awaitable[FSMResult]]
        ] = {
            SessionState.IDLE: self._handle_idle,
            SessionState.START_ADD_PRODUCT: self._handle_idle,
            SessionState.ADD_PRODUCT_NAME: self.add_product_flow.handle_name,
            SessionState.ADD_PRODUCT_PRICE: self.add_product_flow.handle_price,
            SessionState.ADD_PRODUCT_QTY: self.add_product_flow.handle_qty,
            SessionState.CONFIRM_ADD_PRODUCT: self.add_product_flow.handle_confirm,
            # Record Sale Flow
            SessionState.RECORD_SALE_PRODUCT: self.record_sale_flow.handle_sale_product_name,
            SessionState.RECORD_SALE_PRODUCT_SELECTION: (
                self.record_sale_flow.handle_sale_product_selection
            ),
            SessionState.RECORD_SALE_QTY: self.record_sale_flow.handle_sale_product_qty,
            SessionState.CONFIRM_SALE: self.record_sale_flow.handle_confirm_sale_product,
            # Daily Report Flow
            SessionState.REPORT_PENDING: self._handle_idle,
        }

    async def process_message(self, session: UserSession, message_text: str) -> FSMResult:
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
            raise InvalidInputError("Type 'add product' or 'record sale' to begin.")

        session.context.flow_started_at = datetime.now(timezone.utc)

        if intent is Intent.RECORD_SALE:
            self._transition(session, SessionState.RECORD_SALE_PRODUCT)
            return self._build_result(
                previous_state=previous_state,
                session=session,
                reply_text="Great, let's record a sale. What product was sold?",
            )

        if intent is Intent.GENERATE_REPORT:
            self._transition(session, SessionState.REPORT_PENDING)
            await self.generate_report_flow.handle_daily_report(session, message_text)
            self._transition(session, SessionState.IDLE)
            return self._build_result(
                previous_state=previous_state,
                session=session,
                reply_text=(
                    "Great. The report is being generated. "
                    "Just a moment while we process and send it to you."
                ),
            )

        self._transition(session, SessionState.ADD_PRODUCT_NAME)

        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text="Great, let's add a product. What is the product name?",
        )
