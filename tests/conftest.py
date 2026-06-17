import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F403, F401
from app.models.product import Product
from tests.factories import ProductFactory, ShopFactory


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
async def engine():
    """Create a session-scoped engine with NullPool."""
    engine = create_async_engine(
        settings.test_db_url,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


"""
@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session
"""


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a function-scoped database session"""
    async with engine.connect() as conn:
        transaction = await conn.begin()

        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            autoflush=False,
        )

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient for testing FastAPI endpoints."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def shop(db_session):
    shop = ShopFactory.build()
    db_session.add(shop)
    await db_session.flush()
    return shop


@pytest.fixture
async def product(db_session, shop):
    product = Product(
        **ProductFactory.as_dict(),
        shop_id=shop.id,
        sku="PR-TEST",
    )
    db_session.add(product)
    await db_session.flush()
    return product
