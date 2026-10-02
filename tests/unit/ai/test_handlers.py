from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.contracts.period import PeriodType, RelativePeriod, ReportingPeriod
from app.ai.contracts.tools import (
    GetLowStockItemsInput,
    GetSalesSummaryInput,
    GetSlowMovingItemsInput,
    GetStockLevelInput,
    GetTopProductsInput,
    RankingDimension,
)
from app.ai.errors import ProductNotFoundError
from app.ai.handlers.sales_handlers import (
    handle_get_sales_summary,
    handle_get_top_products,
)
from app.ai.handlers.stock_handlers import (
    handle_get_low_stock_items,
    handle_get_slow_moving_items,
    handle_get_stock_level,
)
from app.dto.sales import (
    LowStockProductDTO,
    RevenueSummary,
    SlowMovingProductDTO,
    TopProductByRevenue,
    TopProductByUnits,
)
from app.models.inventory import Inventory
from app.models.product import Product


@pytest.mark.asyncio
async def test_handle_get_sales_summary():
    mock_db = AsyncMock()
    shop_id = uuid4()
    period = ReportingPeriod(period_type=PeriodType.RELATIVE, relative_period=RelativePeriod.MONTH)

    with patch(
        "app.ai.handlers.sales_handlers.sales_repo.get_total_revenue_and_count"
    ) as mock_repo:
        mock_repo.return_value = RevenueSummary(revenue=Decimal("12500.50"), transaction_count=42)

        res = await handle_get_sales_summary(shop_id, GetSalesSummaryInput(period=period), mock_db)
        assert res.total_revenue == Decimal("12500.50")
        assert res.transaction_count == 42


@pytest.mark.asyncio
async def test_handle_get_sales_summary_zero_sales():
    mock_db = AsyncMock()
    shop_id = uuid4()
    period = ReportingPeriod(period_type=PeriodType.RELATIVE, relative_period=RelativePeriod.DAY)

    with patch(
        "app.ai.handlers.sales_handlers.sales_repo.get_total_revenue_and_count"
    ) as mock_repo:
        mock_repo.return_value = RevenueSummary(revenue=Decimal("0.00"), transaction_count=0)

        res = await handle_get_sales_summary(shop_id, GetSalesSummaryInput(period=period), mock_db)
        assert res.total_revenue == Decimal("0.00")
        assert res.transaction_count == 0


@pytest.mark.asyncio
async def test_handle_get_top_products():
    mock_db = AsyncMock()
    shop_id = uuid4()
    p1 = uuid4()
    period = ReportingPeriod(period_type=PeriodType.RELATIVE, relative_period=RelativePeriod.MONTH)

    with patch("app.ai.handlers.sales_handlers.sales_repo.get_top_moving_products") as mock_repo:
        mock_repo.return_value = (
            [TopProductByUnits(product_id=p1, name="Bread", units_sold=50)],
            [TopProductByRevenue(product_id=p1, name="Bread", revenue=Decimal("3000.00"))],
        )

        inp = GetTopProductsInput(period=period, ranking_dimension=RankingDimension.UNITS, limit=3)
        res = await handle_get_top_products(shop_id, inp, mock_db)

        assert res.units is not None
        assert len(res.units) == 1
        assert res.units[0].name == "Bread"
        assert res.revenue is None


@pytest.mark.asyncio
async def test_handle_get_stock_level_not_found():
    mock_db = AsyncMock()
    mock_db.get.return_value = None  # Product not found

    inp = GetStockLevelInput(product_id=uuid4())
    with pytest.raises(ProductNotFoundError):
        await handle_get_stock_level(uuid4(), inp, mock_db)


@pytest.mark.asyncio
async def test_handle_get_stock_level():
    shop_id = uuid4()
    product_id = uuid4()
    product = Product(id=product_id, shop_id=shop_id, name="Milk", price=Decimal("120.00"))
    inventory = Inventory(
        product_id=product_id,
        quantity=2,
        low_stock_threshold=5,
    )
    mock_db = AsyncMock()
    mock_db.get.return_value = product
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = inventory
    mock_db.execute.return_value = execute_result

    result = await handle_get_stock_level(
        shop_id,
        GetStockLevelInput(product_id=product_id),
        mock_db,
    )

    assert result.product_id == product_id
    assert result.quantity == 2
    assert result.is_low_stock is True


@pytest.mark.asyncio
async def test_handle_get_low_stock_items():
    mock_db = AsyncMock()
    shop_id = uuid4()

    dto = LowStockProductDTO(id=uuid4(), name="Milk", quantity=2, low_stock_threshold=5)

    with patch(
        "app.ai.handlers.stock_handlers.sales_repo.get_products_with_low_stock"
    ) as mock_repo:
        mock_repo.return_value = [dto]

        res = await handle_get_low_stock_items(shop_id, GetLowStockItemsInput(), mock_db)
        assert res.count == 1
        assert res.items[0].product_name == "Milk"
        assert res.items[0].current_stock == 2


@pytest.mark.asyncio
async def test_handle_get_slow_moving_items_uses_sales_repository():
    mock_db = AsyncMock()
    shop_id = uuid4()
    product_id = uuid4()
    period = ReportingPeriod(period_type=PeriodType.RELATIVE, relative_period=RelativePeriod.MONTH)
    dto = SlowMovingProductDTO(
        product_id=product_id,
        product_name="Milk",
        units_sold=1,
        current_stock=2,
        unit_price=Decimal("120.00"),
    )

    with patch("app.ai.handlers.stock_handlers.sales_repo.get_slow_moving_products") as mock_repo:
        mock_repo.return_value = [dto]

        result = await handle_get_slow_moving_items(
            shop_id,
            GetSlowMovingItemsInput(period=period, max_sales_count=2, limit=3),
            mock_db,
        )

    assert result.count == 1
    assert result.items[0].product_id == product_id
    assert result.items[0].units_sold == 1
    mock_repo.assert_awaited_once()
