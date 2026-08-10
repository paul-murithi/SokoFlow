from decimal import Decimal

import pytest

from app.fsm.models import SessionContext, SessionState, UserSession
from app.models.inventory import Inventory
from app.models.product import Product
from tests.fixtures.factories import ProductFactory, ShopFactory


@pytest.fixture
async def shop(db_session):
    shop = ShopFactory.build()
    db_session.add(shop)
    await db_session.flush()
    return shop


@pytest.fixture
async def product(db_session, shop):
    product = Product(
        **ProductFactory.as_dict(),
        shop_id=shop.id,
        sku="PR-TEST",
    )
    db_session.add(product)
    await db_session.flush()
    return product


@pytest.fixture
async def inventory(db_session, product):
    inventory = Inventory(product_id=product.id, quantity=10)
    db_session.add(inventory)
    await db_session.flush()

    return inventory


@pytest.fixture
def sale_setup(db_session, shop):
    async def create(
        *,
        price=Decimal("100.50"),
        quantity=10,
    ):
        product = Product(**ProductFactory.as_dict(price=price), shop_id=shop.id, sku="PR-TEST")

        db_session.add(product)
        await db_session.flush()

        inventory = Inventory(
            product_id=product.id,
            quantity=quantity,
        )

        db_session.add(inventory)
        await db_session.flush()

        return {
            "shop": shop,
            "product": product,
            "inventory": inventory,
        }

    return create


@pytest.fixture
def session():
    return UserSession(
        phone="+254700000000",
        state=SessionState.RECORD_SALE_PRODUCT,
        context=SessionContext(product_name="Sugar"),
    )


@pytest.fixture
def idle_session():
    return UserSession(
        phone="+254700000001",
        state=SessionState.IDLE,
        context=SessionContext(),
    )
