from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateShop(BaseModel):
    name: str
    phone: str


class ShopResponse(BaseModel):
    id: UUID
    name: str
    phone: str
    locale: str

    model_config = ConfigDict(from_attributes=True)
