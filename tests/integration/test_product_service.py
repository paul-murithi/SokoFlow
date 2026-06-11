from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from tests.factories import ProductFactory, ShopFactory


async def test_create_product(
    client: AsyncClient,
    db_session: AsyncSession,
):
    shop_payload = ShopFactory.as_dict()
    shop_response = await client.post("/shops", json=shop_payload)
    assert shop_response.status_code == 201
    shop_id = shop_response.json()["id"]

    payload = {**ProductFactory.as_dict(), "shop_id": shop_id}
    response = await client.post("/products", json=payload)

    assert response.status_code == 201
    data = response.json()
    product = await db_session.get(Product, data["id"])
    assert product is not None
    assert product.name == payload["name"]
    assert product.price == Decimal(payload["price"])
    assert product.shop_id == UUID(shop_id)


async def test_create_product_invalid_price(client: AsyncClient, db_session: AsyncSession):
    shop_payload = ShopFactory.as_dict()
    shop_response = await client.post("/shops", json=shop_payload)
    shop_id = shop_response.json()["id"]

    payload = {**ProductFactory.as_dict(price=-222), "shop_id": shop_id}
    response = await client.post("/products", json=payload)

    assert response.status_code == 422


async def test_get_product_not_found(client: AsyncClient):
    random_uuid = uuid4()
    response = await client.get(f"/products/{random_uuid}")

    assert response.status_code == 404
    assert response.json()["detail"] == f"Product with ID {
        random_uuid} not found"
