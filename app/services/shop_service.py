from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shop import Shop
from app.schemas.shop import CreateShop, UpdateShopLocale
from app.utils.errors import ResourceAlreadyExistsException


class ShopService:
    async def create_shop(self, data: CreateShop, db: AsyncSession) -> Shop:
        shop = Shop(phone=data.phone, name=data.name, locale=data.locale.value)
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

    async def update_locale(self, phone: str, data: UpdateShopLocale, db: AsyncSession) -> Shop:
        shop = (await db.execute(select(Shop).where(Shop.phone == phone))).scalar_one_or_none()
        if shop is None:
            shop = Shop(phone=phone, name="SokoFlow Demo Shop")
            db.add(shop)

        shop.locale = data.locale.value
        await db.commit()
        await db.refresh(shop)
        return shop
