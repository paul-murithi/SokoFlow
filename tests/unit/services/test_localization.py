from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.fsm.models import FSMResult, MessageKey, SessionContext, SessionState
from app.schemas.shop import CreateShop
from app.services.localization import render_message


def test_shop_locale_defaults_to_english() -> None:
    shop = CreateShop(name="Kibanda", phone="+254700000000")

    assert shop.locale.value == "en"


def test_shop_accepts_swahili_locale() -> None:
    shop = CreateShop(name="Kibanda", phone="+254700000000", locale="sw")

    assert shop.locale.value == "sw"


def test_shop_rejects_unsupported_locale() -> None:
    with pytest.raises(ValidationError):
        CreateShop(name="Kibanda", phone="+254700000000", locale="fr")


def test_parameterized_message_renders_in_both_locales() -> None:
    params = {"product_name": "Sugar", "price": Decimal("120.00"), "quantity": 3}

    assert render_message(MessageKey.CONFIRM_PRODUCT, "en", params) == (
        "Please confirm: Sugar at KES 120.00, quantity 3. Reply Yes or No."
    )
    assert render_message(MessageKey.CONFIRM_PRODUCT, "sw", params) == (
        "Thibitisha: Sugar kwa KES 120.00, kiasi 3. Jibu Yes au No."
    )


def test_same_semantic_result_renders_for_shop_locale() -> None:
    result = FSMResult(
        previous_state=SessionState.CONFIRM_SALE,
        new_state=SessionState.IDLE,
        context=SessionContext(),
        message_key=MessageKey.SALE_RECORDED,
        message_params={
            "product_name": "Sugar",
            "quantity": 3,
            "remaining_stock": 10,
            "entered_low_stock": True,
        },
    )

    english = render_message(result.message_key, "en", result.message_params)
    swahili = render_message(result.message_key, "sw", result.message_params)

    assert english == (
        "Sale recorded: *Sugar* (3 units).\n"
        "Stock remaining: *10* units.\n*Low Stock Alert*: Only 10 units left."
    )
    assert swahili == (
        "Mauzo yamerekodiwa: *Sugar* (3 vipande).\n"
        "Stoo iliyobaki: *10* vipande.\n*Tahadhari ya Stoo ya Chini*: Zimesalia vipande 10 tu."
    )
