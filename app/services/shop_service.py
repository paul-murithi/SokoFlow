from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shop import Shop
from app.schemas.shop import CreateShop
from app.utils.errors import ResourceAlreadyExistsException


class ShopService:
    async def create_shop(self, data: CreateShop, db: AsyncSession) -> Shop:
        shop = Shop(phone=data.phone, name=data.name)
        db.add(shop)

        try:
            await db.commit()
            await db.refresh(shop)
            return shop
        except IntegrityError:
            await db.rollback()
            raise ResourceAlreadyExistsException(
                entity_name="Shop", field_name="phone", value=data.phone
            )
