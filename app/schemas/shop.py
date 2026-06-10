from uuid import UUID

from pydantic import BaseModel


class CreateShop(BaseModel):
    name: str
    phone: str


class ShopResponse(BaseModel):
    id: UUID
    name: str
    phone: str
    locale: str
