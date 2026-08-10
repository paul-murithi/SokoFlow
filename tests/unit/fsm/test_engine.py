import pytest

from app.fsm.engine import FSMEngine
from app.fsm.intent_resolver import Intent, IntentResolver
from app.fsm.models import SessionContext, SessionState, UserSession


@pytest.mark.asyncio
async def test_cancel_override_resets_flow_keeps_history() -> None:
    engine = FSMEngine()
    session = UserSession(
        phone="+254700000100",
        state=SessionState.ADD_PRODUCT_PRICE,
        context=SessionContext(
            product_name="Sugar",
            product_price="120.00",
            product_qty=2,
            error_count=2,
            history=[SessionState.IDLE, SessionState.ADD_PRODUCT_NAME],
        ),
    )

    result = await engine.process_message(session, " cancel ")

    assert result.reply_text == "Flow cancelled. How can I help you today?"
    assert result.previous_state == SessionState.ADD_PRODUCT_PRICE
    assert result.new_state == SessionState.IDLE
    assert result.context.error_count == 0
    assert result.context.product_name is None
    assert result.context.product_price is None
    assert result.context.product_qty is None
    assert result.context.history == [
        SessionState.IDLE,
        SessionState.ADD_PRODUCT_NAME,
        SessionState.ADD_PRODUCT_PRICE,
    ]


@pytest.mark.asyncio
async def test_invalid_input_keeps_state_and_increments_errors() -> None:
    engine = FSMEngine()
    session = UserSession(
        phone="+254700000101",
        state=SessionState.ADD_PRODUCT_PRICE,
        context=SessionContext(product_name="Sugar", error_count=0),
    )

    result = await engine.process_message(session, "not-a-price")

    assert result.previous_state == SessionState.ADD_PRODUCT_PRICE
    assert result.new_state == SessionState.ADD_PRODUCT_PRICE
    assert result.context.error_count == 1
    assert result.reply_text == ("Please enter a valid price, e.g. '150', 'KES 150', or '150/='.")


@pytest.mark.asyncio
async def test_process_message_max_invalid_attempts_resets_to_idle() -> None:
    engine = FSMEngine()
    session = UserSession(
        phone="+254700000102",
        state=SessionState.ADD_PRODUCT_PRICE,
        context=SessionContext(
            product_name="Rice",
            product_price="99.50",
            product_qty=1,
            error_count=2,
            history=[SessionState.IDLE],
        ),
    )

    result = await engine.process_message(session, "wrong-price")

    assert result.previous_state == SessionState.ADD_PRODUCT_PRICE
    assert result.new_state == SessionState.IDLE
    assert result.context.error_count == 0
    assert result.context.product_name is None
    assert result.context.product_price is None
    assert result.context.product_qty is None
    assert result.reply_text == (
        "Too many invalid attempts. I've cancelled this request so we can start "
        "fresh. Type 'add product' to try again."
    )


@pytest.mark.asyncio
async def test_process_message_add_product_happy_path() -> None:
    engine = FSMEngine()
    session = UserSession(
        phone="+254700000103",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    start_result = await engine.process_message(session, "add product")
    name_result = await engine.process_message(session, "Sugar")
    price_result = await engine.process_message(session, "150")
    qty_result = await engine.process_message(session, "12")
    confirm_result = await engine.process_message(session, "yes")

    assert start_result.new_state == SessionState.ADD_PRODUCT_NAME
    assert name_result.new_state == SessionState.ADD_PRODUCT_PRICE
    assert price_result.new_state == SessionState.ADD_PRODUCT_QTY
    assert qty_result.new_state == SessionState.CONFIRM_ADD_PRODUCT
    assert "Please confirm:" in qty_result.reply_text

    assert confirm_result.new_state == SessionState.IDLE
    assert confirm_result.context.product_name is None
    assert confirm_result.context.product_price is None
    assert confirm_result.context.product_qty is None
    assert confirm_result.reply_text == (
        "Product added: Sugar at KES 150.00 with opening quantity 12."
    )


def test_intent_resolver_classifies_messy_add_product_phrases() -> None:
    resolver = IntentResolver()

    assert resolver.resolve("Please help me add a new product") is Intent.ADD_PRODUCT
    assert resolver.resolve("I want to register item") is Intent.ADD_PRODUCT
    assert resolver.resolve("") is Intent.UNKNOWN


@pytest.mark.asyncio
async def test_idle_state_uses_intent_resolver_for_add_product_flow() -> None:
    engine = FSMEngine()
    session = UserSession(
        phone="+254700000104",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    result = await engine.process_message(session, "can you help me add a new product please")

    assert result.new_state == SessionState.ADD_PRODUCT_NAME
    assert result.reply_text == "Great, let's add a product. What is the product name?"


@pytest.mark.asyncio
async def test_idle_state_uses_intent_resolver_for_record_sale_flow() -> None:
    engine = FSMEngine()
    session = UserSession(
        phone="+254700000105",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    result = await engine.process_message(session, "record sale")

    assert result.new_state == SessionState.RECORD_SALE_PRODUCT
    assert result.reply_text == "Great, let's record a sale. What product was sold?"


@pytest.mark.asyncio
async def test_record_sale_confirmation_cancel_resets_flow() -> None:
    engine = FSMEngine()
    session = UserSession(
        phone="+254700000106",
        state=SessionState.CONFIRM_SALE,
        context=SessionContext(
            product_name="Sugar",
            product_price="120.00",
            product_qty=2,
            history=[SessionState.IDLE],
        ),
    )

    result = await engine.process_message(session, "no")

    assert result.previous_state == SessionState.CONFIRM_SALE
    assert result.new_state == SessionState.IDLE
    assert result.reply_text == "No problem. I cancelled the sale flow."
    assert result.context.product_name is None
    assert result.context.product_price is None
    assert result.context.product_qty is None


@pytest.mark.asyncio
async def test_record_sale_invalid_selection_stays_in_selection_state() -> None:
    engine = FSMEngine()
    session = UserSession(
        phone="+254700000107",
        state=SessionState.RECORD_SALE_PRODUCT_SELECTION,
        context=SessionContext(
            product_candidates=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "shop_id": "22222222-2222-2222-2222-222222222222",
                    "name": "Sugar",
                    "sku": "SUG-001",
                    "price": "120.00",
                    "similarity_score": 0.98,
                }
            ]
        ),
    )

    result = await engine.process_message(session, "9")

    assert result.previous_state == SessionState.RECORD_SALE_PRODUCT_SELECTION
    assert result.new_state == SessionState.RECORD_SALE_PRODUCT_SELECTION
    assert result.context.error_count == 1
    assert result.reply_text == "Invalid Choice"
