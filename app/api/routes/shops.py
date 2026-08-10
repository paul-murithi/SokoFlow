from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.shop import CreateShop, ShopResponse
from app.services.shop_service import ShopService

router = APIRouter()
service = ShopService()


@router.post("", status_code=201, response_model=ShopResponse)
async def create_shop(payload: CreateShop, db: AsyncSession = Depends(get_db)) -> ShopResponse:
    shop = await service.create_shop(payload, db)
    return ShopResponse.model_validate(shop)
