"""Integration tests verifying full round-trip execution across all 7 analytics query tools.

Tests the complete WhatsApp conversation path:
Inbound WhatsApp Payload -> conversation_task -> FSMEngine (AnalyticsRoutingPolicy -> AnalyticsFlow)
-> AnalyticsOrchestrator -> ToolExecutor -> ToolRegistry -> Database / Handlers
-> AnalyticsFormatter -> Localization -> Outbound MessageSender.
"""

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts.llm import LLMResponse, NormalizedToolCall
from app.ai.llm_client import LLMClient
from app.core.config import settings
from app.fsm.conversation_store import ConversationStore
from app.fsm.session_lua import register_session_update_script
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.sales import Sale
from app.models.shop import Shop
from app.workers.conversation_tasks import conversation


@pytest.fixture(autouse=True)
def patch_worker_db(db_session: AsyncSession, monkeypatch):
    @asynccontextmanager
    async def fake_worker_db():
        yield db_session

    monkeypatch.setattr("app.workers.conversation_tasks.get_worker_db", fake_worker_db)


@pytest.fixture(autouse=True)
async def setup_redis(monkeypatch):
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    register_session_update_script(client)
    store = ConversationStore(redis=client)
    monkeypatch.setattr("app.workers.conversation_tasks.get_conversation_store", lambda: store)
    yield
    keys = await client.keys("session:*")
    if keys:
        await client.delete(*keys)
    await client.aclose()


@pytest.fixture
async def analytics_shop_data(db_session: AsyncSession):
    """Sets up a test shop with products, inventory, and sales records."""
    shop_phone = "+254711223344"
    shop = Shop(
        id=uuid4(),
        phone=shop_phone,
        name="Mama Mboga Store",
        locale="en",
    )
    db_session.add(shop)

    # 1. Milk 500ml (low stock)
    prod_milk500 = Product(
        id=uuid4(),
        shop_id=shop.id,
        name="Fresh Milk 500ml",
        price=Decimal("60.00"),
        sku="FM-500",
    )
    # 2. Milk 1L (normal stock)
    prod_milk1l = Product(
        id=uuid4(),
        shop_id=shop.id,
        name="Fresh Milk 1L",
        price=Decimal("110.00"),
        sku="FM-1000",
    )
    # 3. Sugar 1kg (top selling)
    prod_sugar = Product(
        id=uuid4(),
        shop_id=shop.id,
        name="Sugar 1kg",
        price=Decimal("150.00"),
        sku="SUG-1",
    )
    # 4. Salt 500g (slow moving)
    prod_salt = Product(
        id=uuid4(),
        shop_id=shop.id,
        name="Iodized Salt 500g",
        price=Decimal("35.00"),
        sku="SALT-500",
    )

    db_session.add_all([prod_milk500, prod_milk1l, prod_sugar, prod_salt])
    await db_session.flush()

    inv1 = Inventory(product_id=prod_milk500.id, quantity=2, low_stock_threshold=5)
    inv2 = Inventory(product_id=prod_milk1l.id, quantity=15, low_stock_threshold=5)
    inv3 = Inventory(product_id=prod_sugar.id, quantity=20, low_stock_threshold=5)
    inv4 = Inventory(product_id=prod_salt.id, quantity=50, low_stock_threshold=5)
    db_session.add_all([inv1, inv2, inv3, inv4])

    # Add sales for sugar (top product)
    sale1 = Sale(
        id=uuid4(),
        shop_id=shop.id,
        product_id=prod_sugar.id,
        quantity=10,
        unit_price=Decimal("150.00"),
        recorded_by="Test",
    )
    sale2 = Sale(
        id=uuid4(),
        shop_id=shop.id,
        product_id=prod_sugar.id,
        quantity=5,
        unit_price=Decimal("150.00"),
        recorded_by="Test",
    )
    db_session.add_all([sale1, sale2])
    await db_session.commit()

    return {
        "shop": shop,
        "phone": shop_phone,
        "prod_milk500": prod_milk500,
        "prod_milk1l": prod_milk1l,
        "prod_sugar": prod_sugar,
        "prod_salt": prod_salt,
    }


def make_inbound_payload(phone: str, message: str) -> dict[str, object]:
    return {
        "sender": phone,
        "message_text": message,
        "message_id": f"wamid.{uuid4()}",
        "correlation_id": str(uuid4()),
    }


@pytest.mark.asyncio
async def test_roundtrip_all_7_tools(analytics_shop_data, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test_key")
    phone = analytics_shop_data["phone"]

    # Tool 1: get_sales_summary
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_sales_summary",
                    arguments={"period": {"period_type": "relative", "relative_period": "day"}},
                )
            ]
        )
        reply = await conversation(make_inbound_payload(phone, "How are sales today?"))
        assert "KES" in reply
        assert "sales summary" in reply.lower() or "today" in reply.lower()

    # Tool 2: get_stock_level
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_stock_level",
                    arguments={"product_name": "Sugar 1kg"},
                )
            ]
        )
        reply = await conversation(
            make_inbound_payload(phone, "How much sugar do we have left in stock?")
        )
        assert "Sugar 1kg" in reply
        assert "20 units" in reply

    # Tool 3: get_top_products
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_top_products",
                    arguments={"period": {"period_type": "relative", "relative_period": "day"}},
                )
            ]
        )
        reply = await conversation(make_inbound_payload(phone, "What are my best sellers today?"))
        assert "Sugar 1kg" in reply
        assert "15 units" in reply

    # Tool 4: get_low_stock_items
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[NormalizedToolCall(name="get_low_stock_items", arguments={})]
        )
        reply = await conversation(make_inbound_payload(phone, "What's running low on stock?"))
        assert "Low Stock Alert" in reply
        assert "Fresh Milk 500ml" in reply

    # Tool 5: get_sales_trend
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_sales_trend",
                    arguments={"period": {"period_type": "relative", "relative_period": "week"}},
                )
            ]
        )
        reply = await conversation(make_inbound_payload(phone, "Did I sell more than last week?"))
        assert "Sales trend" in reply
        assert "Revenue" in reply

    # Tool 6: get_slow_moving_items
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_slow_moving_items",
                    arguments={"period": {"period_type": "relative", "relative_period": "month"}},
                )
            ]
        )
        reply = await conversation(make_inbound_payload(phone, "What hasn't sold this month?"))
        assert "Slow-moving products" in reply
        assert "Iodized Salt 500g" in reply or "Fresh Milk" in reply

    # Tool 7: get_product_price
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_product_price",
                    arguments={"product_name": "Sugar 1kg"},
                )
            ]
        )
        reply = await conversation(make_inbound_payload(phone, "How much is Sugar 1kg?"))
        assert "Sugar 1kg" in reply
        assert "KES 150.00" in reply
        assert "SUG-1" in reply


@pytest.mark.asyncio
async def test_roundtrip_multi_turn_follow_up(analytics_shop_data, monkeypatch):
    """Tests multi-turn follow-up retaining prior analytics context across turns."""
    monkeypatch.setattr(settings, "groq_api_key", "test_key")
    phone = analytics_shop_data["phone"]

    # Turn 1: Primary query
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_sales_summary",
                    arguments={"period": {"period_type": "relative", "relative_period": "day"}},
                )
            ]
        )
        reply1 = await conversation(make_inbound_payload(phone, "Sales today?"))
        assert "KES" in reply1

    # Turn 2: Follow-up question ("and yesterday?")
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_sales_summary",
                    arguments={"period": {"period_type": "relative", "relative_period": "day"}},
                )
            ]
        )
        reply2 = await conversation(make_inbound_payload(phone, "and yesterday?"))
        assert "KES" in reply2
        # Verify LLMClient was given the assistant's prior context
        call_kwargs = mock_gen.call_args.kwargs
        messages = call_kwargs["messages"]
        assert any("get_sales_summary" in (m.content or "") for m in messages)


@pytest.mark.asyncio
async def test_roundtrip_disambiguation_choice(analytics_shop_data, monkeypatch):
    """Tests product disambiguation prompting followed by option selection."""
    monkeypatch.setattr(settings, "groq_api_key", "test_key")
    phone = analytics_shop_data["phone"]

    # Turn 1: Ambiguous product name "milk"
    with patch.object(LLMClient, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            tool_calls=[
                NormalizedToolCall(
                    name="get_product_price",
                    arguments={"product_name": "Fresh Milk"},
                )
            ]
        )
        reply1 = await conversation(make_inbound_payload(phone, "How much is Fresh Milk?"))
        # Should prompt user to select between Fresh Milk 500ml and Fresh Milk 1L
        assert "1." in reply1
        assert "Fresh Milk 500ml" in reply1
        assert "Fresh Milk 1L" in reply1

    # Turn 2: User responds with selection "1"
    reply2 = await conversation(make_inbound_payload(phone, "1"))
    # Should resolve to candidate 1 (Fresh Milk 1L) without calling LLM
    assert "Fresh Milk 1L" in reply2
    assert "KES 110.00" in reply2
    assert "FM-1000" in reply2
