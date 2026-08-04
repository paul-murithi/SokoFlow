import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

url = make_url(os.getenv("DATABASE_URL", settings.database_url))

# Force the driver to asyncpg
if url.drivername in ("postgresql", "postgres", "postgresql+psycopg2"):
    url = url.set(drivername="postgresql+asyncpg")

engine = create_async_engine(url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


# FastAPI DI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


# Worker DB
@asynccontextmanager
async def get_worker_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
