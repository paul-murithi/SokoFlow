from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.fsm.fsm_utils import (
    parse_confirmation,
    parse_price,
    parse_product_name,
    parse_quantity,
)
from app.fsm.models import FSMResult, SessionState, UserSession
from app.fsm.primitives import FSMPrimitives
from app.schemas.product import ProductCreate
from app.services.product_service import ProductService
from app.utils.errors import InvalidInputError


class AddProductFlow(FSMPrimitives):
    def __init__(
        self,
        db_session: AsyncSession | None = None,
        product_service: ProductService | None = None,
    ) -> None:
        self.db = db_session
        self.product_service = product_service or ProductService()

    async def handle_name(self, session: UserSession, message_text: str) -> FSMResult:
        previous_state = session.state

        session.context.product_name = parse_product_name(message_text)
        self._transition(session, SessionState.ADD_PRODUCT_PRICE)

        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text="Nice. What is the price in KES?",
        )

    async def handle_price(self, session: UserSession, message_text: str) -> FSMResult:
        previous_state = session.state

        session.context.product_price = parse_price(message_text)
        self._transition(session, SessionState.ADD_PRODUCT_QTY)

        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text="Got it. How many units are in stock?",
        )

    async def handle_qty(self, session: UserSession, message_text: str) -> FSMResult:
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

    async def handle_confirm(
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
