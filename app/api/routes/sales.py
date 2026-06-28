from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.sales import SaleCreate, SaleResponse
from app.services.sales_service import SalesService

router = APIRouter()
service = SalesService()


@router.post("", response_model=SaleResponse, status_code=201)
async def record_sale(
    payload: SaleCreate, db: AsyncSession = Depends(get_db)
) -> SaleResponse:
    sale = await service.record_sale(
        shop_id=payload.shop_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        db=db,
        recorded_by=payload.recorded_by,
    )
    return SaleResponse.model_validate(sale)
