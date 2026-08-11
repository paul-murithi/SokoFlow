from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_worker_db
from app.fsm.fsm_utils import parse_product_name
from app.fsm.models import (
    FSMResult,
    ProductResolutionStatus,
    ScoredProductMatch,
    SessionState,
    UserSession,
)
from app.fsm.primitives import FSMPrimitives
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService
from app.utils.errors import CorruptedSessionError


class StockLookupFlow(FSMPrimitives):
    def __init__(
        self,
        db_session: AsyncSession | None = None,
        product_service: ProductService | None = None,
        inventory_service: InventoryService | None = None,
    ) -> None:
        self.product_service = product_service or ProductService()
        self.inventory_service = inventory_service or InventoryService()
        self.db_session = db_session

    async def handle_stock_name(self, session: UserSession, message: str) -> FSMResult:
        product_name = parse_product_name(message)
        previous_state = session.state

        async with self._get_db_session() as db:
            shop_id = await self.get_shop_id(db=db, sender=session.phone)
            session.context.shop_id = shop_id

            matches = await self.product_service.find_products_by_fuzzy_name(
                db=db,
                shop_id=shop_id,
                query=product_name,
            )

        match matches.status:
            case ProductResolutionStatus.NOT_FOUND:
                session.context.product_candidates = []
                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    reply_text="I could not find a product in the inventory with that name.",
                )
            case ProductResolutionStatus.AMBIGUOUS:
                candidates = matches.candidates
                if not candidates:
                    raise CorruptedSessionError(session.phone)

                session.context.product_candidates = candidates

                reply_message = self._format_product_choices(candidates)
                self._transition(
                    session=session,
                    new_state=SessionState.CHECK_STOCK_PRODUCT_SELECTION,
                )
                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    reply_text=reply_message,
                )

            case ProductResolutionStatus.EXACT_MATCH:
                if matches.product is None:
                    raise CorruptedSessionError(session.phone)

                quantity, product_name = await self._get_inventory(
                    db=db,
                    phone=session.phone,
                    product=matches.product,
                )
                self._transition(
                    session=session,
                    new_state=SessionState.IDLE,
                )
                self._clear_context_preserving_history(session)
                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    reply_text=f"Remaining stock for {product_name}: {quantity} units",
                )

    async def handle_stock_product_selection(self, session: UserSession, message: str) -> FSMResult:
        previous_state = session.state
        selected_product = self._resolve_product_choice(session, message)

        session.context.product_id = selected_product.id
        session.context.product_name = selected_product.name
        session.context.product_price = selected_product.price

        async with self._get_db_session() as db:
            quantity, product_name = await self._get_inventory(
                db=db,
                phone=session.phone,
                product=selected_product,
            )

        self._transition(session=session, new_state=SessionState.IDLE)
        self._clear_context_preserving_history(session)
        return self._build_result(
            previous_state=previous_state,
            session=session,
            reply_text=f"Remaining stock for {product_name}: {quantity} units",
        )

    async def _get_inventory(
        self,
        *,
        db: AsyncSession,
        phone: str,
        product: ScoredProductMatch | None = None,
    ) -> tuple[int, str]:
        if product is None:
            raise CorruptedSessionError(phone)
        inventory = await self.inventory_service.get_stock(
            product_id=product.id,
            db=db,
        )
        return inventory.quantity, product.name

    @asynccontextmanager  # pyright: ignore[reportDeprecated]
    async def _get_db_session(self) -> AsyncIterator[AsyncSession]:
        if self.db_session is not None:
            yield self.db_session
            return

        async with get_worker_db() as db_session:
            yield db_session
