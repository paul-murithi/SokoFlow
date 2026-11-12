from typing import cast

from redis.asyncio import Redis

from app.core.config import settings


def make_redis_client() -> Redis:
    """Factory that creates a fresh Redis client.

    Production code should call this function to obtain a client that will be
    used for the analytics rate‑limiter. In tests it can be replaced with a mock
    or a client that is scoped to the fixture.
    """
    # TODO: Unnecessary cast call.
    # TODO:
    # Investigate newer Redis versions to see whether from_url() gained explicit return annotation
    return cast(
        Redis,
        Redis.from_url(settings.redis_url, decode_responses=True),
    )


# Backward‑compatible singleton used by legacy code – Not used by the
# new FSMEngine but is kept for any other parts of the codebase that still call
# get_redis().
redis_client: Redis = make_redis_client()


def get_redis() -> Redis:
    return redis_client
