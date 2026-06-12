from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
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


async def test_create_product_invalid_price(
    client: AsyncClient, db_session: AsyncSession
):
    shop_id = uuid4()

    payload = {**ProductFactory.as_dict(price=-222), "shop_id": str(shop_id)}
    response = await client.post("/products", json=payload)

    assert response.status_code == 422


async def test_get_product_not_found(client: AsyncClient):
    random_uuid = uuid4()
    response = await client.get(f"/products/{random_uuid}")

    assert response.status_code == 404
    assert response.json()["detail"] == f"Product with ID {random_uuid} not found"


async def test_duplicate_sku_constraint_enforced_at_db_level(
    client: AsyncClient, db_session: AsyncSession
):
    shop_payload = ShopFactory.as_dict()
    shop_response = await client.post("/shops", json=shop_payload)
    shop_id = shop_response.json()["id"]

    product_payload = {**ProductFactory.as_dict(), "shop_id": shop_id}
    first_response = await client.post("/products", json=product_payload)
    generated_sku = first_response.json()["sku"]

    duplicate = Product(
        name="Another Product", price=9.99, sku=generated_sku, shop_id=shop_id
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_create_product_with_duplicate_sku_returns_409(client: AsyncClient):
    shop_payload = ShopFactory.as_dict()
    shop_response = await client.post("/shops", json=shop_payload)
    shop_id = shop_response.json()["id"]

    product_payload = {**ProductFactory.as_dict(), "shop_id": shop_id}

    fixed_sku = "PROD-TEST-001"

    with patch(
        "app.services.product_service.ProductService.generate_sku",
        return_value=fixed_sku,
    ):
        first = await client.post("/products", json=product_payload)
        assert first.status_code == 201
        assert first.json()["sku"] == fixed_sku

        second = await client.post("/products", json=product_payload)
        assert second.status_code == 409
        assert "duplicate" in second.json()["detail"].lower()
