from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.services.inventory_service import InventoryService
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
