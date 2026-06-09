from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.schemas.product import ProductCreate, ProductResponse
from app.services.product_service import ProductService
from app.core.database import get_db

router = APIRouter()
service = ProductService()


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
        payload: ProductCreate,
        db: AsyncSession = Depends(get_db)
) -> ProductResponse:
    return await service.create_product(payload, db)


@router.get("")
def get_products() -> None: ...


@router.get("/{id}")
def get_product(id: UUID) -> None: ...


@router.patch("/{id}")
def update_product(id: UUID) -> None: ...


@router.delete("/{id}")
def delete_product(id: UUID) -> None: ...
