from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.fsm.flows.record_sale import RecordSaleFlow
from app.fsm.models import (
    ProductResolution,
    ProductResolutionStatus,
    ScoredProductMatch,
    SessionContext,
    SessionState,
    UserSession,
)
from app.utils.errors import InvalidInputError


class StubProductService:
    def __init__(self, resolution: ProductResolution) -> None:
        self.resolution = resolution
        self.calls: list[dict[str, object]] = []

    async def find_products_by_fuzzy_name(self, *, db, shop_id, query):
        self.calls.append({"db": db, "shop_id": shop_id, "query": query})
        return self.resolution


class StubSalesService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def record_sale(self, *, shop_id, product_id, quantity, db) -> None:
        self.calls.append(
            {
                "shop_id": shop_id,
                "product_id": product_id,
                "quantity": quantity,
                "db": db,
            }
        )


@pytest.mark.asyncio
async def test_handle_sale_product_name_exact_match_transitions_to_quantity_prompt() -> None:
    shop_id = uuid4()
    product_id = uuid4()
    resolution = ProductResolution(
        status=ProductResolutionStatus.EXACT_MATCH,
        product=ScoredProductMatch(
            id=product_id,
            shop_id=shop_id,
            name="Sugar",
            sku="SUG-001",
            price=Decimal("120.00"),
            similarity_score=0.99,
        ),
    )
    flow = RecordSaleFlow(
        db_session=object(),
        product_service=StubProductService(resolution),
        sales_service=StubSalesService(),
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)
    session = UserSession(
        phone="+254700000200",
        state=SessionState.RECORD_SALE_PRODUCT,
        context=SessionContext(),
    )

    result = await flow.handle_sale_product_name(session, "Sugar")

    assert result.previous_state == SessionState.RECORD_SALE_PRODUCT
    assert result.new_state == SessionState.RECORD_SALE_QTY
    assert result.reply_text == "Got it. How many units sold?"
    assert session.context.product_id == product_id
    assert session.context.product_name == "Sugar"
    assert session.context.product_price == Decimal("120.00")


@pytest.mark.asyncio
async def test_handle_sale_product_selection_moves_to_quantity_state() -> None:
    selected_product = ScoredProductMatch(
        id=uuid4(),
        shop_id=uuid4(),
        name="Rice",
        sku="RIC-001",
        price=Decimal("80.50"),
        similarity_score=0.95,
    )
    flow = RecordSaleFlow(
        db_session=object(),
        product_service=StubProductService(
            ProductResolution(status=ProductResolutionStatus.NOT_FOUND)
        ),
        sales_service=StubSalesService(),
    )
    session = UserSession(
        phone="+254700000201",
        state=SessionState.RECORD_SALE_PRODUCT_SELECTION,
        context=SessionContext(product_candidates=[selected_product]),
    )

    result = await flow.handle_sale_product_selection(session, "1")

    assert result.previous_state == SessionState.RECORD_SALE_PRODUCT_SELECTION
    assert result.new_state == SessionState.RECORD_SALE_QTY
    assert result.reply_text == "Got it. How many units?"
    assert session.context.product_id == selected_product.id
    assert session.context.product_name == selected_product.name
    assert session.context.product_price == selected_product.price


@pytest.mark.asyncio
async def test_handle_sale_product_name_not_found_keeps_state_idle() -> None:
    flow = RecordSaleFlow(
        db_session=object(),
        product_service=StubProductService(
            ProductResolution(status=ProductResolutionStatus.NOT_FOUND)
        ),
        sales_service=StubSalesService(),
    )
    flow.get_shop_id = AsyncMock(return_value=uuid4())
    session = UserSession(
        phone="+254700000202",
        state=SessionState.RECORD_SALE_PRODUCT,
        context=SessionContext(),
    )

    result = await flow.handle_sale_product_name(session, "Unknown")

    assert result.previous_state == SessionState.RECORD_SALE_PRODUCT
    assert result.new_state == SessionState.RECORD_SALE_PRODUCT
    assert "I couldn't find a matching product" in result.reply_text
    assert session.context.product_id is None


@pytest.mark.asyncio
async def test_handle_sale_product_selection_rejects_invalid_choice() -> None:
    flow = RecordSaleFlow(
        db_session=object(),
        product_service=StubProductService(
            ProductResolution(status=ProductResolutionStatus.NOT_FOUND)
        ),
        sales_service=StubSalesService(),
    )
    session = UserSession(
        phone="+254700000203",
        state=SessionState.RECORD_SALE_PRODUCT_SELECTION,
        context=SessionContext(
            product_candidates=[
                ScoredProductMatch(
                    id=uuid4(),
                    shop_id=uuid4(),
                    name="Rice",
                    sku="RIC-001",
                    price=Decimal("80.50"),
                    similarity_score=0.95,
                )
            ]
        ),
    )

    with pytest.raises(InvalidInputError, match="Invalid Choice"):
        flow._resolve_product_choice(session, "9")


@pytest.mark.asyncio
async def test_handle_confirm_sale_product_cancel_clears_context() -> None:
    flow = RecordSaleFlow(
        db_session=object(),
        product_service=StubProductService(
            ProductResolution(status=ProductResolutionStatus.NOT_FOUND)
        ),
        sales_service=StubSalesService(),
    )
    session = UserSession(
        phone="+254700000204",
        state=SessionState.CONFIRM_SALE,
        context=SessionContext(
            product_name="Sugar",
            product_price=Decimal("120.00"),
            product_qty=2,
            history=[SessionState.IDLE],
        ),
    )

    result = await flow.handle_confirm_sale_product(session, "no")

    assert result.previous_state == SessionState.CONFIRM_SALE
    assert result.new_state == SessionState.IDLE
    assert result.reply_text == "No problem. I cancelled the sale flow."
    assert result.context.product_name is None
    assert result.context.product_price is None
    assert result.context.product_qty is None


@pytest.mark.asyncio
async def test_handle_confirm_sale_product_persists_sale_record() -> None:
    shop_id = uuid4()
    product_id = uuid4()
    sales_service = StubSalesService()
    flow = RecordSaleFlow(
        db_session=object(),
        product_service=StubProductService(
            ProductResolution(status=ProductResolutionStatus.NOT_FOUND)
        ),
        sales_service=sales_service,
    )
    session = UserSession(
        phone="+254700000205",
        state=SessionState.CONFIRM_SALE,
        context=SessionContext(
            shop_id=shop_id,
            product_id=product_id,
            product_name="Sugar",
            product_price=Decimal("120.00"),
            product_qty=3,
            history=[SessionState.IDLE],
        ),
    )

    result = await flow.handle_confirm_sale_product(session, "yes")

    assert result.new_state == SessionState.IDLE
    assert result.reply_text == ("Sale recorded: Sugar at KES 120.00 units sold 3.")
    assert len(sales_service.calls) == 1
    assert sales_service.calls[0]["shop_id"] == shop_id
    assert sales_service.calls[0]["product_id"] == product_id
    assert sales_service.calls[0]["quantity"] == 3
    assert result.context.product_name is None
