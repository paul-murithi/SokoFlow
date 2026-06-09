from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import ProductFactory
from app.models.product import Product


async def test_create_product(
    client: AsyncClient,
    db: AsyncSession,
):
    payload = ProductFactory.as_dict()

    response = await client.post("/products", json=payload)

    assert response.status_code == 201

    data = response.json()

    product = await db.get(Product, data["id"])

    assert product is not None
    assert product.name == payload["name"]
    assert product.price == payload["price"]
