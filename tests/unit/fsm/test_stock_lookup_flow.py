from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.fsm.flows.stock_lookup import StockLookupFlow
from app.fsm.models import (
    ProductResolution,
    ProductResolutionStatus,
    ScoredProductMatch,
    SessionContext,
    SessionState,
    UserSession,
)


class StubProductService:
    def __init__(self, resolution: ProductResolution) -> None:
        self.resolution = resolution
        self.calls: list[dict[str, object]] = []

    async def find_products_by_fuzzy_name(self, *, db, shop_id, query):
        self.calls.append({"db": db, "shop_id": shop_id, "query": query})
        return self.resolution


class StubInventoryService:
    def __init__(self, quantity: int = 12) -> None:
        self.quantity = quantity
        self.calls: list[dict[str, object]] = []

    async def get_stock(self, *, product_id, db):
        self.calls.append({"product_id": product_id, "db": db})

        class Inventory:
            def __init__(self, quantity: int) -> None:
                self.quantity = quantity

        return Inventory(self.quantity)


@pytest.mark.asyncio
async def test_handle_stock_name_uses_fallback_db_session_when_not_injected(monkeypatch) -> None:
    shop_id = uuid4()
    product_id = uuid4()
    db_session = object()
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

    @asynccontextmanager
    async def fake_worker_db():
        yield db_session

    monkeypatch.setattr("app.fsm.flows.stock_lookup.get_worker_db", fake_worker_db)

    flow = StockLookupFlow(
        db_session=None,
        product_service=StubProductService(resolution),
        inventory_service=StubInventoryService(quantity=7),
    )
    flow.get_shop_id = AsyncMock(return_value=shop_id)
    session = UserSession(
        phone="+254700000300",
        state=SessionState.CHECK_STOCK_PRODUCT,
        context=SessionContext(),
    )

    result = await flow.handle_stock_name(session, "Sugar")

    assert result.previous_state == SessionState.CHECK_STOCK_PRODUCT
    assert result.new_state == SessionState.IDLE
    assert result.reply_text == "Remaining stock for Sugar: 7 units"
    assert flow.product_service.calls[0]["db"] is db_session
    assert flow.inventory_service.calls[0]["db"] is db_session
    assert session.context.shop_id == shop_id
    assert session.context.product_id is None
    assert session.context.product_candidates == []


@pytest.mark.asyncio
async def test_handle_stock_product_selection_clears_selection_context_after_reply() -> None:
    shop_id = uuid4()
    selected_product = ScoredProductMatch(
        id=uuid4(),
        shop_id=shop_id,
        name="Rice",
        sku="RIC-001",
        price=Decimal("80.50"),
        similarity_score=0.95,
    )
    flow = StockLookupFlow(
        db_session=object(),
        product_service=StubProductService(
            ProductResolution(status=ProductResolutionStatus.NOT_FOUND)
        ),
        inventory_service=StubInventoryService(quantity=4),
    )
    session = UserSession(
        phone="+254700000301",
        state=SessionState.CHECK_STOCK_PRODUCT_SELECTION,
        context=SessionContext(
            shop_id=shop_id,
            product_candidates=[selected_product],
        ),
    )

    result = await flow.handle_stock_product_selection(session, "1")

    assert result.previous_state == SessionState.CHECK_STOCK_PRODUCT_SELECTION
    assert result.new_state == SessionState.IDLE
    assert result.reply_text == "Remaining stock for Rice: 4 units"
    assert session.context.shop_id == shop_id
    assert session.context.product_id is None
    assert session.context.product_name is None
    assert session.context.product_candidates == []
