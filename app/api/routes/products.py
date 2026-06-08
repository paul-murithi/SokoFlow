from uuid import UUID

from fastapi import APIRouter

from app.schemas.product import ProductCreate, ProductResponse
from app.services.product_service import ProductService

router = APIRouter()
service = ProductService()


@router.post("", status_code=201, response_model=ProductResponse)
def create_product(product: ProductCreate) -> None: ...


@router.get("")
def get_products() -> None: ...


@router.get("/{id}")
def get_product(id: UUID) -> None: ...


@router.patch("/{id}")
def update_product(id: UUID) -> None: ...


@router.delete("/{id}")
def delete_product(id: UUID) -> None: ...
