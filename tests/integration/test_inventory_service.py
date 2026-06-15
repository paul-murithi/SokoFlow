from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from tests.factories import ProductFactory, ShopFactory


async def test_create_inventory(client: AsyncClient, db_session: AsyncSession):
    shop = ShopFactory.build()
    db_session.add(shop)
    await db_session.flush()

    product_factory = ProductFactory.as_dict()
    product = Product(**product_factory, sku="PR-TEST", shop_id=shop.id)
    db_session.add(product)
    await db_session.flush()

    assert shop.id is not None
    assert product.id is not None
    # TODO: Add the product to the inventory table.
    # Get the product_id back
    # Test add stock
