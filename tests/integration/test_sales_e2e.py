from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

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
