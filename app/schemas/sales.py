from decimal import Decimal

from pydantic import BaseModel


class SaleCreate(BaseModel):
    shop_id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    recorded_by: str
