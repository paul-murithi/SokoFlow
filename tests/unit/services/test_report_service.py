from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.report_service import ReportService
from app.services.sales_service import SalesService

report_service = ReportService()
sales_service = SalesService()


@pytest.mark.asyncio
async def test_get_daily_report_data(db_session: AsyncSession, sale_setup):
    data = await sale_setup(price=Decimal("100.00"), quantity=50)
    product = data["product"]
    shop = data["shop"]

    # Record sale
    await sales_service.record_sale(shop.id, product.id, 2, db_session)

    report_data = await report_service.get_daily_report_data(
        shop.id, datetime.now(timezone.utc), db_session
    )
    assert report_data["total_revenue"] == Decimal("200.00")
    assert report_data["transaction_count"] == 1
