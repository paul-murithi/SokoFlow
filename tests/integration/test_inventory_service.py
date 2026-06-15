from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import ProductFactory, ShopFactory


async def test_create_inventory(client: AsyncClient, db_session: AsyncSession):
    shop_payload = ShopFactory.as_dict()
    shop_response = await client.post("/shops", json=shop_payload)
    shop_id = shop_response.json()["id"]

    product_payload = {**ProductFactory.as_dict(), "shop_id": shop_id}
    product_response = await client.post("/products", json=product_payload)
    product_id = product_response.json()["id"]

    assert shop_id and product_id is not None
    # TODO: Add the product to the inventory table.
    # Get the product_id back
    # Test add stock
