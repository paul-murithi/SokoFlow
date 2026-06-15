from uuid import UUID

from pydantic import BaseModel, Field


class CreateInventory(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class InventoryResponse(BaseModel):
    id: UUID
    product_id: UUID
    quantity: int
