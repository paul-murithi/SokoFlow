import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.models.product import Product
from app.services.inventory_service import InventoryService
from app.utils.errors import InsufficientStockException
from tests.factories import ProductFactory, ShopFactory

inventory_service = InventoryService()


async def test_create_inventory(client: AsyncClient, db_session: AsyncSession):
    shop = ShopFactory.build()
    db_session.add(shop)
    await db_session.flush()

    product_factory = ProductFactory.as_dict()
    product = Product(**product_factory, sku="PR-TEST", shop_id=shop.id)
    db_session.add(product)
    await db_session.flush()

    assert product.id is not None

    quantity_to_add = 10
    old_quantity = 0

    updated_inventory = await inventory_service.add_stock(
        product_id=product.id, quantity=quantity_to_add, db=db_session
    )

    assert updated_inventory.quantity == old_quantity + quantity_to_add
    assert product.id == updated_inventory.product_id

    await db_session.refresh(updated_inventory)
    assert updated_inventory.quantity == 10


async def test_deduct_stock(client: AsyncClient, db_session: AsyncSession, product):
    old_quantity = 10
    quantity_to_deduct = 3

    inventory = Inventory(product_id=product.id, quantity=old_quantity)
    db_session.add(inventory)
    await db_session.flush()

    await inventory_service.deduct_stock(
        product.id, quantity=quantity_to_deduct, db=db_session
    )

    result = await db_session.execute(
        select(Inventory).where(Inventory.product_id == product.id)
    )
    persisted_inventory = result.scalar_one()

    assert persisted_inventory.product_id == product.id
    assert persisted_inventory.quantity == old_quantity - quantity_to_deduct


async def test_deduct_insufficient_stock(
    client: AsyncClient, db_session: AsyncSession, product
):
    inventory = Inventory(product_id=product.id)
    db_session.add(inventory)
    await db_session.flush()

    # TODO: Validate for quantity > 0 at the API layer
    quantity_to_deduct = 6

    with pytest.raises(InsufficientStockException):
        await inventory_service.deduct_stock(
            product.id, quantity_to_deduct, db=db_session
        )


def test_deduct_stock_alert_threshold(
    client: AsyncClient, db_session: AsyncSession
): ...
