from decimal import Decimal

from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.services.inventory_service import InventoryService
from app.services.sales_service import SalesService

sales_service = SalesService()
inventory_service = InventoryService()


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


async def test_get_products_with_low_stock(db_session: AsyncSession, shop):
    product_1 = Product(
        shop_id=shop.id,
        name="Product 1",
        price=Decimal("100.50"),
        sku="PR-TEST-1"
    )
    
    db_session.add(product_1)

    product_2 = Product(
        shop_id=shop.id,
        name="Product 2",
        price=Decimal("100.50"),
        sku="PR-TEST-2"
    )

    product_3 = Product(
        shop_id=shop.id,
        name="Product 3",
        price=Decimal("100.50"),
        sku="PR-TEST-3"
    )

    db_session.add(product_2)
    db_session.add(product_3)

    await db_session.flush([product_1, product_2, product_3])

    # Add inventory
    await inventory_service.add_stock(product_1.id, 10, db_session)
    await inventory_service.add_stock(product_2.id, 10, db_session)
    await inventory_service.add_stock(product_3.id, 10, db_session)

    # Deduct stock
    await inventory_service.deduct_stock(product_1.id, 6, db_session)
    await inventory_service.deduct_stock(product_2.id, 6, db_session)

    # assert
    products = await sales_service.get_products_with_low_stock(shop.id, db_session)
    assert len(products) == 2
    assert {p.id for p in products} == {product_1.id, product_2.id}

    for product in products:
        assert product.id is not None
        assert all(p.quantity == 4 for p in products)
        assert all(p.low_stock_threshold == 5 for p in products)
