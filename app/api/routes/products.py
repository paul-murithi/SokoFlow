from uuid import UUID

from fastapi import APIRouter

router = APIRouter()


@router.post("")
def create_product() -> None: ...


@router.get("")
def get_products() -> None: ...


@router.get("/{id}")
def get_product(id: UUID) -> None: ...


@router.patch("/{id}")
def update_product(id: UUID) -> None: ...


@router.delete("/{id}")
def delete_product(id: UUID) -> None: ...
