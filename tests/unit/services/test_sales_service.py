import pytest
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sales_service import SalesService
from app.models.sales import Sale
from app.utils.errors import ResourceNotFoundException

sales_service = SalesService()


@pytest.mark.asyncio
async def test_record_sale_with_recorded_by(db_session: AsyncSession, sale_setup):
    data = await sale_setup(price=Decimal("50.00"), quantity=20)
    product = data["product"]
    shop = data["shop"]

    sale = await sales_service.record_sale(
        shop_id=shop.id,
        product_id=product.id,
        quantity=5,
        db=db_session,
        recorded_by="Alice",
    )

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
async def test_get_daily_summary(db_session: AsyncSession, sale_setup):
    data = await sale_setup(price=Decimal("10.00"), quantity=100)
    product = data["product"]
    shop = data["shop"]

    # Record 2 sales
    await sales_service.record_sale(shop.id, product.id, 5, db_session)
    await sales_service.record_sale(shop.id, product.id, 10, db_session)

    summary = await sales_service.get_daily_summary(shop.id, datetime.now(timezone.utc), db_session)
    
    assert summary["total_revenue"] == Decimal("150.00")
    assert summary["transaction_count"] == 2
    assert summary["top_product_by_units"]["product_id"] == product.id
    assert summary["top_product_by_units"]["units_sold"] == 15
    assert summary["top_product_by_revenue"]["product_id"] == product.id
    assert summary["top_product_by_revenue"]["revenue"] == Decimal("150.00")


@pytest.mark.asyncio
async def test_get_daily_summary_empty(db_session: AsyncSession, shop):
    summary = await sales_service.get_daily_summary(shop.id, datetime.now(timezone.utc), db_session)
    
    assert summary["total_revenue"] == Decimal("0.00")
    assert summary["transaction_count"] == 0
    assert summary["top_product_by_units"] is None
    assert summary["top_product_by_revenue"] is None
