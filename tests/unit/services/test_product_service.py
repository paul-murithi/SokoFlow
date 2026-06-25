import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.product_service import ProductService
from app.schemas.product import ProductCreate, ProductUpdate
from app.models.product import Product
from app.utils.errors import ResourceAlreadyExistsException, ResourceNotFoundException
from tests.factories import ProductFactory, ShopFactory

product_service = ProductService()


@pytest.mark.asyncio
async def test_create_product_success(db_session: AsyncSession, shop):
    data = ProductCreate(
        name="Unit Test Product",
        price=Decimal("199.99"),
        shop_id=shop.id,
    )
    product = await product_service.create_product(data, db_session)
    assert product.name == "Unit Test Product"
    assert product.price == Decimal("199.99")
    assert product.shop_id == shop.id
    assert product.sku is not None


@pytest.mark.asyncio
async def test_create_product_duplicate_sku(db_session: AsyncSession, shop):
    data = ProductCreate(
        name="Duplicate SKU Product",
        price=Decimal("15.50"),
        shop_id=shop.id,
    )
    
    with patch.object(db_session, "commit", side_effect=IntegrityError("stmt", "params", Exception())):
        with pytest.raises(ResourceAlreadyExistsException):
            await product_service.create_product(data, db_session)


@pytest.mark.asyncio
async def test_get_product_success(db_session: AsyncSession, product):
    fetched = await product_service.get_product(product.id, db_session)
    assert fetched.id == product.id
    assert fetched.name == product.name


@pytest.mark.asyncio
async def test_get_product_not_found(db_session: AsyncSession):
    random_id = uuid4()
    with pytest.raises(ResourceNotFoundException):
        await product_service.get_product(random_id, db_session)


@pytest.mark.asyncio
async def test_list_products(db_session: AsyncSession, shop):
    p1 = Product(name="Item 1", price=Decimal("10.00"), sku="SKU-1", shop_id=shop.id)
    p2 = Product(name="Item 2", price=Decimal("20.00"), sku="SKU-2", shop_id=shop.id)
    db_session.add_all([p1, p2])
    await db_session.flush()

    products = await product_service.list_products(shop.id, db_session)
    assert len(products) >= 2
    assert any(p.name == "Item 1" for p in products)
    assert any(p.name == "Item 2" for p in products)


@pytest.mark.asyncio
async def test_update_product_success(db_session: AsyncSession, product):
    update_data = ProductUpdate(
        name="Updated Name",
        price=Decimal("299.99"),
    )
    original_sku = product.sku
    updated = await product_service.update_product(product.id, update_data, db_session)
    
    assert updated.name == "Updated Name"
    assert updated.price == Decimal("299.99")
    assert updated.sku != original_sku


@pytest.mark.asyncio
async def test_update_product_price_only_keeps_sku(db_session: AsyncSession, product):
    update_data = ProductUpdate(
        price=Decimal("49.99"),
    )
    original_name = product.name
    original_sku = product.sku
    updated = await product_service.update_product(product.id, update_data, db_session)
    
    assert updated.name == original_name
    assert updated.price == Decimal("49.99")
    assert updated.sku == original_sku


@pytest.mark.asyncio
async def test_update_product_not_found(db_session: AsyncSession):
    random_id = uuid4()
    update_data = ProductUpdate(name="Missing")
    with pytest.raises(ResourceNotFoundException):
        await product_service.update_product(random_id, update_data, db_session)


@pytest.mark.asyncio
async def test_delete_product_success(db_session: AsyncSession, product):
    # Verify product exists
    p = await db_session.get(Product, product.id)
    assert p is not None

    # Delete
    await product_service.delete_product(product.id, db_session)

    # Verify deleted
    p_deleted = await db_session.get(Product, product.id)
    assert p_deleted is None


@pytest.mark.asyncio
async def test_delete_product_not_found(db_session: AsyncSession):
    random_id = uuid4()
    with pytest.raises(ResourceNotFoundException):
        await product_service.delete_product(random_id, db_session)
