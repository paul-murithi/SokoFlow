from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_worker_db
from app.fsm.fsm_utils import parse_confirmation, parse_quantity
from app.fsm.models import (
    FSMResult,
    ProductResolutionStatus,
    SessionState,
    UserSession,
)
from app.fsm.primitives import FSMPrimitives
from app.services.product_service import ProductService
from app.services.sales_service import SalesService
from app.utils.errors import (
    CorruptedSessionError,
    InvalidInputError,
    ResourceConflictException,
    ResourceNotFoundException,
)


class RecordSaleFlow(FSMPrimitives):
    def __init__(
        self,
        db_session: AsyncSession | None = None,
        product_service: ProductService | None = None,
        sales_service: SalesService | None = None,
    ) -> None:
        self.db_session = db_session
        self.product_service = product_service or ProductService()
        self.sales_service = sales_service or SalesService()

    async def handle_sale_product_name(self, session: UserSession, message: str) -> FSMResult:
        previous_state = session.state

        async with self._get_db_session(db_session=self.db_session) as db:
            shop_id = await self.get_shop_id(db=db, sender=session.phone)
            session.context.shop_id = shop_id
            matches = await self.product_service.find_products_by_fuzzy_name(
                db=db,
                shop_id=shop_id,
                query=message,
            )

        match matches.status:
            case ProductResolutionStatus.EXACT_MATCH:
                # Happy path - 1 product found - Confident match
                if matches.product is None:
                    raise CorruptedSessionError(session.phone)

                session.context.product_id = matches.product.id
                session.context.product_name = matches.product.name
                session.context.product_price = matches.product.price
                self._transition(session, SessionState.RECORD_SALE_QTY)
                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    reply_text="Got it. How many units sold?",
                )
            case ProductResolutionStatus.AMBIGUOUS:
                # Multiple candidates
                session.context.product_candidates = matches.candidates
                self._transition(session, SessionState.RECORD_SALE_PRODUCT_SELECTION)

                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    reply_text=self._format_product_choices(matches.candidates),
                )
            case ProductResolutionStatus.NOT_FOUND:
                # No close match
                reply_text = """
                    I couldn't find a matching product.
                    Would you like to add it first?
                    Type 'add product' to add it, or try another product name.
                """
                return self._build_result(
                    previous_state=previous_state, session=session, reply_text=reply_text
                )

    async def handle_sale_product_selection(self, session: UserSession, message: str) -> FSMResult:
        previous_state = session.state
        selected_product = self._resolve_product_choice(session, message)
        session.context.product_id = selected_product.id
        session.context.product_name = selected_product.name
        session.context.product_price = selected_product.price

        self._transition(session=session, new_state=SessionState.RECORD_SALE_QTY)
        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text="Got it. How many units?",
        )

    async def handle_sale_product_qty(self, session: UserSession, message: str) -> FSMResult:
        quantity = parse_quantity(message)
        if quantity <= 0:
            raise InvalidInputError("Please enter a quantity greater than 0.")

        session.context.product_qty = quantity
        previous_state = session.state
        product_name = session.context.product_name
        product_price = session.context.product_price

        if product_name is None or product_price is None:
            raise InvalidInputError(
                "I lost some product details. Type 'record sale' to start again."
            )

        self._transition(session=session, new_state=SessionState.CONFIRM_SALE)
        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text=(
                f"Please confirm: {product_name} at KES {product_price:.2f}, "
                f"units sold {session.context.product_qty}. Reply Yes or No."
            ),
        )

    async def handle_confirm_sale_product(self, session: UserSession, message: str) -> FSMResult:
        previous_state = session.state

        is_confirmed = parse_confirmation(message)
        if not is_confirmed:
            self._transition(session, SessionState.IDLE)
            self._clear_context_preserving_history(session)
            return self._build_result(
                previous_state=previous_state,
                session=session,
                reply_text="No problem. I cancelled the sale flow.",
            )

        product_name = session.context.product_name
        product_price = session.context.product_price
        units_sold = session.context.product_qty

        if product_name is None or product_price is None or units_sold is None:
            raise InvalidInputError(
                "I lost some product details. Type 'record sale' to start again."
            )

        try:
            await self._persist_product_db(session)
        except (
            InvalidInputError,
            ResourceConflictException,
            ResourceNotFoundException,
        ) as exc:
            raise InvalidInputError(str(exc)) from exc

        self._transition(session, SessionState.IDLE)
        self._clear_context_preserving_history(session)
        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text=(
                f"Sale recorded: {product_name} at KES {product_price:.2f} units sold {units_sold}."
            ),
        )

    async def _persist_product_db(self, session: UserSession) -> None:
        if self.db_session is not None:
            await self._persist_product_db_with_session(session=session, db=self.db_session)
            return

        async with get_worker_db() as db_session:
            await self._persist_product_db_with_session(session=session, db=db_session)

    async def _persist_product_db_with_session(
        self,
        session: UserSession,
        db: AsyncSession,
    ) -> None:
        shop_id = session.context.shop_id
        product_id = session.context.product_id
        units_sold = session.context.product_qty

        if shop_id is None or product_id is None or units_sold is None:
            raise InvalidInputError(
                "I lost some product details. Type 'record sale' to start again."
            )

        await self.sales_service.record_sale(
            shop_id=shop_id,
            product_id=product_id,
            quantity=units_sold,
            db=db,
        )
