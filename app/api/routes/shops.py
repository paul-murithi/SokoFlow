from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.shop import Shop
from app.schemas.shop import CreateShop, ShopResponse

router = APIRouter()


@router.post("", status_code=201, response_model=ShopResponse)
async def create_shop(payload: CreateShop, db: AsyncSession = Depends(get_db)) -> Shop:
    # TODO: Move to service layer and correct response type
    shop = Shop(phone=payload.phone, name=payload.name)

    db.add(shop)
    await db.commit()
    await db.refresh(shop)

    return shop
