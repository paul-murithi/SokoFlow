from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sales_service import SalesService
from app.utils.errors import ResourceConflictException, ResourceNotFoundException

sales_service = SalesService()


@pytest.mark.asyncio
async def test_record_sale_with_recorded_by(db_session: AsyncSession, sale_setup):
    data = await sale_setup(price=Decimal("50.00"), quantity=20)
    product = data["product"]
    shop = data["shop"]

    result = await sales_service.record_sale(
        shop_id=shop.id,
        product_id=product.id,
        quantity=5,
        db=db_session,
        recorded_by="Alice",
    )
    sale = result.sale

    assert sale.product_id == product.id
    assert sale.quantity == 5
    assert sale.unit_price == Decimal("50.00")
    assert sale.total == Decimal("250.00")
    assert sale.recorded_by == "Alice"


@pytest.mark.asyncio
async def test_record_sale_product_not_found(db_session: AsyncSession):
    random_id = uuid4()
    with pytest.raises(ResourceNotFoundException):
        await sales_service.record_sale(
            shop_id=uuid4(),
            product_id=random_id,
            quantity=5,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_record_sale_shop_mismatch(db_session: AsyncSession, sale_setup):
    data = await sale_setup(price=Decimal("50.00"), quantity=20)
    product = data["product"]

    with pytest.raises(ResourceConflictException):
        await sales_service.record_sale(
            shop_id=uuid4(),
            product_id=product.id,
            quantity=5,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_get_daily_summary(db_session: AsyncSession, sale_setup):
    data = await sale_setup(price=Decimal("10.00"), quantity=100)
    product = data["product"]
    shop = data["shop"]

    # Record 2 sales
    await sales_service.record_sale(shop.id, product.id, 5, db_session)
    await sales_service.record_sale(shop.id, product.id, 10, db_session)

    summary = await sales_service.get_daily_summary(shop.id, datetime.now(timezone.utc), db_session)

    assert summary.total_revenue == Decimal("150.00")
    assert summary.transaction_count == 2
    assert len(summary.top_products_by_units) == 1
    assert summary.top_products_by_units[0].product_id == product.id
    assert summary.top_products_by_units[0].name == product.name
    assert summary.top_products_by_units[0].units_sold == 15
    assert len(summary.top_products_by_revenue) == 1
    assert summary.top_products_by_revenue[0].product_id == product.id
    assert summary.top_products_by_revenue[0].name == product.name
    assert summary.top_products_by_revenue[0].revenue == Decimal("150.00")


@pytest.mark.asyncio
async def test_get_daily_summary_empty(db_session: AsyncSession, shop):
    summary = await sales_service.get_daily_summary(shop.id, datetime.now(timezone.utc), db_session)

    assert summary.total_revenue == Decimal("0.00")
    assert summary.transaction_count == 0
    assert summary.top_products_by_units == []
    assert summary.top_products_by_revenue == []


@pytest.mark.asyncio
async def test_get_daily_summary_multiple_top_moving_products_tied(
    db_session: AsyncSession, sale_setup
):
    data = await sale_setup(price=Decimal("10.00"), quantity=100)
    product1 = data["product"]
    shop = data["shop"]

    # Create a second product and inventory in the same shop
    from app.models.inventory import Inventory
    from app.models.product import Product

    product2 = Product(shop_id=shop.id, name="Product 2", price=Decimal("10.00"), sku="PR-TIED-2")
    db_session.add(product2)
    await db_session.flush()

    inventory2 = Inventory(product_id=product2.id, quantity=100)
    db_session.add(inventory2)
    await db_session.flush()

    # Record sales for both products with equal quantity and revenue
    await sales_service.record_sale(shop.id, product1.id, 5, db_session)
    await sales_service.record_sale(shop.id, product2.id, 5, db_session)

    summary = await sales_service.get_daily_summary(shop.id, datetime.now(timezone.utc), db_session)

    assert summary.total_revenue == Decimal("100.00")
    assert summary.transaction_count == 2
    """
    Both products should be returned since they are tied
        for top moving product by units and revenue
    """
    assert len(summary.top_products_by_units) == 2
    units_product_ids = {p.product_id for p in summary.top_products_by_units}
    assert units_product_ids == {product1.id, product2.id}

    assert len(summary.top_products_by_revenue) == 2
    revenue_product_ids = {p.product_id for p in summary.top_products_by_revenue}
    assert revenue_product_ids == {product1.id, product2.id}
