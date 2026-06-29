from decimal import Decimal
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
from fastapi import status

from app.services.sales_service import SalesService

sales_service = SalesService()


async def test_record_sale(db_session: AsyncSession, sale_setup):
    data = await sale_setup()

    product = data["product"]
    shop = data["shop"]

    quantity_to_deduct = 10

    # Create sale
    sale = await sales_service.record_sale(
        shop_id=shop.id,
        product_id=product.id,
        quantity=quantity_to_deduct,
        db=db_session,
    )

    expected_total = quantity_to_deduct * sale.unit_price

    assert sale.product_id == product.id
    assert sale.total == expected_total
    assert sale.unit_price == Decimal(product.price)


async def test_record_sale_api(client: AsyncClient, sale_setup):
    setup_data = await sale_setup()
    product = setup_data["product"]
    shop = setup_data["shop"]

    payload = {
        "shop_id": str(shop.id),
        "product_id": str(product.id),
        "quantity": 5,
        "recorded_by": "API User",
    }
    response = await client.post("/sales", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["recorded_by"] == "API User"
    assert data["quantity"] == 5
    assert Decimal(data["total"]) == Decimal(product.price) * 5


async def test_daily_report_api(client: AsyncClient, sale_setup):
    setup_data = await sale_setup(price=Decimal("20.00"))
    product = setup_data["product"]
    shop = setup_data["shop"]

    # Record two sales via API
    payload1 = {
        "shop_id": str(shop.id),
        "product_id": str(product.id),
        "quantity": 2,
    }
    response1 = await client.post("/sales", json=payload1)
    assert response1.status_code == status.HTTP_201_CREATED

    payload2 = {
        "shop_id": str(shop.id),
        "product_id": str(product.id),
        "quantity": 3,
    }
    response2 = await client.post("/sales", json=payload2)
    assert response2.status_code == status.HTTP_201_CREATED

    # Fetch daily report
    report_response = await client.get(f"/reports/daily/{shop.id}")
    assert report_response.status_code == status.HTTP_200_OK
    report_data = report_response.json()
    assert Decimal(report_data["total_revenue"]) == Decimal("100.00")
    assert report_data["transaction_count"] == 2
    assert report_data["top_product_by_units"]["product_id"] == str(product.id)
    assert report_data["top_product_by_units"]["units_sold"] == 5
