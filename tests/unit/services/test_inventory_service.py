from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.inventory_service import InventoryService
from app.utils.errors import ResourceNotFoundException

inventory_service = InventoryService()


@pytest.mark.asyncio
async def test_get_stock_success(db_session: AsyncSession, inventory):
    fetched = await inventory_service.get_stock(inventory.product_id, db_session)
    assert fetched.product_id == inventory.product_id
    assert fetched.quantity == inventory.quantity


@pytest.mark.asyncio
async def test_get_stock_not_found(db_session: AsyncSession):
    random_id = uuid4()
    with pytest.raises(ResourceNotFoundException):
        await inventory_service.get_stock(random_id, db_session)


@pytest.mark.asyncio
async def test_update_threshold_success(db_session: AsyncSession, inventory):
    original_threshold = inventory.low_stock_threshold
    assert original_threshold == 5  # default server default in schema / factory

    updated = await inventory_service.update_threshold(inventory.product_id, 10, db_session)
    assert updated.low_stock_threshold == 10

    await db_session.refresh(inventory)
    assert inventory.low_stock_threshold == 10


@pytest.mark.asyncio
async def test_update_threshold_not_found(db_session: AsyncSession):
    random_id = uuid4()
    with pytest.raises(ResourceNotFoundException):
        await inventory_service.update_threshold(random_id, 10, db_session)
