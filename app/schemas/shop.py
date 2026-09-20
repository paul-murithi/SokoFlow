from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.shop import ShopLocale


class CreateShop(BaseModel):
    name: str
    phone: str
    locale: ShopLocale = ShopLocale.ENGLISH


class UpdateShopLocale(BaseModel):
    locale: ShopLocale


class ShopResponse(BaseModel):
    id: UUID
    name: str
    phone: str
    locale: str

    model_config = ConfigDict(from_attributes=True)
