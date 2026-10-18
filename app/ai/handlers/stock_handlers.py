"""Stock and Inventory Tool Handlers.

Executes get_stock_level, get_low_stock_items, and get_slow_moving_items using
existing SokoFlow services and repositories.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts.tools import (
    GetLowStockItemsInput,
    GetLowStockItemsOutput,
    GetProductPriceInput,
    GetProductPriceOutput,
    GetSlowMovingItemsInput,
    GetSlowMovingItemsOutput,
    GetStockLevelInput,
    GetStockLevelOutput,
    LowStockItem,
    SlowMovingItem,
)
from app.ai.errors import ProductAmbiguousError, ProductNotFoundError
from app.ai.handlers.utils import resolve_period_boundaries
from app.ai.product_resolver import ProductResolver
from app.fsm.models import ProductResolutionStatus
from app.models.inventory import Inventory
from app.models.product import Product
from app.repositories.sales_repo import SalesRepository

sales_repo = SalesRepository()
product_resolver = ProductResolver()


async def handle_get_stock_level(
    shop_id: UUID,
    input_data: GetStockLevelInput,
    db: AsyncSession,
) -> GetStockLevelOutput:
    """Retrieves current inventory level, threshold, and price for a resolved product."""
    nil_uuid = UUID("00000000-0000-0000-0000-000000000000")
    product: Product | None = None

    if input_data.product_id and input_data.product_id != nil_uuid:
        product = await db.get(Product, input_data.product_id)
        if product is None or product.shop_id != shop_id:
            raise ProductNotFoundError(input_data.product_id)
    elif input_data.product_name:
        resolution = await product_resolver.resolve_product(
            shop_id=shop_id,
            search_term=input_data.product_name,
            db=db,
        )
        if resolution.status == ProductResolutionStatus.EXACT_MATCH and resolution.product:
            product = await db.get(Product, resolution.product.id)
            if product is None or product.shop_id != shop_id:
                raise ProductNotFoundError(input_data.product_name)
        elif resolution.status == ProductResolutionStatus.AMBIGUOUS:
            raise ProductAmbiguousError(
                search_term=input_data.product_name,
                candidates=resolution.candidates,
            )
        else:
            raise ProductNotFoundError(input_data.product_name)
    else:
        raise ProductNotFoundError("Product identifier not provided")

    stmt = select(Inventory).where(Inventory.product_id == product.id)
    inv_result = await db.execute(stmt)
    inventory = inv_result.scalar_one_or_none()

    qty = inventory.quantity if inventory else 0
    threshold = inventory.low_stock_threshold if inventory else 0

    return GetStockLevelOutput(
        product_id=product.id,
        product_name=product.name,
        quantity=qty,
        low_stock_threshold=threshold,
        unit_price=product.price,
        is_low_stock=(qty <= threshold),
    )


async def handle_get_low_stock_items(
    shop_id: UUID,
    input_data: GetLowStockItemsInput,
    db: AsyncSession,
) -> GetLowStockItemsOutput:
    """Returns products currently at or below their configured low-stock thresholds."""
    low_stock_dtos = await sales_repo.get_products_with_low_stock(shop_id=shop_id, db=db)

    items = [
        LowStockItem(
            product_id=dto.id,
            product_name=dto.name,
            current_stock=dto.quantity,
            low_stock_threshold=dto.low_stock_threshold,
        )
        for dto in low_stock_dtos
    ]

    return GetLowStockItemsOutput(items=items, count=len(items))


async def handle_get_slow_moving_items(
    shop_id: UUID,
    input_data: GetSlowMovingItemsInput,
    db: AsyncSession,
) -> GetSlowMovingItemsOutput:
    """Identifies products with total sales units <= max_sales_count over the period."""
    utc_start, utc_end = resolve_period_boundaries(input_data.period)
    limit = input_data.limit or 10

    rows = await sales_repo.get_slow_moving_products(
        shop_id=shop_id,
        day_start=utc_start,
        day_end=utc_end,
        max_sales_count=input_data.max_sales_count,
        limit=limit,
        db=db,
    )

    items = [
        SlowMovingItem(
            product_id=row.product_id,
            product_name=row.product_name,
            units_sold=row.units_sold,
            current_stock=row.current_stock,
            unit_price=row.unit_price,
        )
        for row in rows
    ]

    return GetSlowMovingItemsOutput(items=items, count=len(items))


async def handle_get_product_price(
    shop_id: UUID,
    input_data: GetProductPriceInput,
    db: AsyncSession,
) -> GetProductPriceOutput:
    """Retrieves selling price and SKU for a resolved product."""
    nil_uuid = UUID("00000000-0000-0000-0000-000000000000")
    product: Product | None = None

    if input_data.product_id and input_data.product_id != nil_uuid:
        product = await db.get(Product, input_data.product_id)
        if product is None or product.shop_id != shop_id:
            raise ProductNotFoundError(input_data.product_id)
    elif input_data.product_name:
        resolution = await product_resolver.resolve_product(
            shop_id=shop_id,
            search_term=input_data.product_name,
            db=db,
        )
        if resolution.status == ProductResolutionStatus.EXACT_MATCH and resolution.product:
            product = await db.get(Product, resolution.product.id)
            if product is None or product.shop_id != shop_id:
                raise ProductNotFoundError(input_data.product_name)
        elif resolution.status == ProductResolutionStatus.AMBIGUOUS:
            raise ProductAmbiguousError(
                search_term=input_data.product_name,
                candidates=resolution.candidates,
            )
        else:
            raise ProductNotFoundError(input_data.product_name)
    else:
        raise ProductNotFoundError("Product identifier not provided")

    return GetProductPriceOutput(
        product_id=product.id,
        product_name=product.name,
        unit_price=product.price,
        sku=product.sku,
    )
