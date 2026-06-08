from httpx import AsyncClient

from tests.factories import ProductFactory


async def test_create_product(client: AsyncClient):
    response = await client.post("/products", json=ProductFactory.as_dict())
    assert response.status_code == 201


async def test_expensive_product(client: AsyncClient):
    response = await client.post(
        "/products", json=ProductFactory.as_dict(price=9999.99)
    )
    assert response.status_code == 201
