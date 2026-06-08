from typing import Any

import redis.asyncio as ioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": "ok",
        "services": {
            "api": "ok",
            "postgres": "unknown",
            "redis": "unknown",
        },
    }

    # Postgres
    try:
        await db.execute(text("SELECT 1"))
        response["services"]["postgres"] = "ok"
    except Exception as e:
        response["services"]["postgres"] = f"error: {e}"
        response["status"] = "degraded"

    # Redis
    try:
        r = ioredis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        response["services"]["redis"] = "ok"
    except Exception as e:
        response["services"]["redis"] = f"error: {e}"
        response["status"] = "degraded"

    return response
