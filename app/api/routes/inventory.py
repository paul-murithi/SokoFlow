from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.inventory import (
    AddStockRequest,
    DeductStockRequest,
    InventoryResponse,
    StockDeductionResult,
    UpdateThresholdRequest,
)
from app.services.inventory_service import InventoryService

router = APIRouter()
service = InventoryService()


@router.get("/{product_id}", response_model=InventoryResponse)
async def get_stock(product_id: UUID, db: AsyncSession = Depends(get_db)) -> InventoryResponse:
    inventory = await service.get_stock(product_id, db)
    return InventoryResponse.model_validate(inventory)


@router.post("/add", response_model=InventoryResponse)
async def add_stock(
    payload: AddStockRequest, db: AsyncSession = Depends(get_db)
) -> InventoryResponse:
    inventory = await service.add_stock(payload.product_id, payload.quantity, db)
    return InventoryResponse.model_validate(inventory)


@router.post("/deduct")
async def deduct_stock(
    payload: DeductStockRequest, db: AsyncSession = Depends(get_db)
) -> StockDeductionResult:
    result = await service.deduct_stock(payload.product_id, payload.quantity, db)
    return StockDeductionResult.model_validate(result)


@router.patch("/{product_id}/threshold", response_model=InventoryResponse)
async def update_threshold(
    product_id: UUID,
    payload: UpdateThresholdRequest,
    db: AsyncSession = Depends(get_db),
) -> InventoryResponse:
    inventory = await service.update_threshold(product_id, payload.low_stock_threshold, db)
    return InventoryResponse.model_validate(inventory)
