import functools
import hashlib
import inspect
import json
import logging
from typing import Any, Callable

from redis import Redis as SyncRedis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL_SECONDS = 3600  # 1 hour


def generate_idempotency_key(
    task_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    key_prefix: str = "idempotency",
) -> str:
    """Generates a deterministic idempotency key from correlation_id, task_id, or task parameters."""
    correlation_id = kwargs.get("correlation_id") or kwargs.get("task_id")
    if not correlation_id and args and isinstance(args[0], dict):
        correlation_id = args[0].get("correlation_id") or args[0].get("task_id")

    if not correlation_id:
        # The fallback must be stable across worker processes and restarts.
        serialized = json.dumps(
            {"args": args, "kwargs": kwargs},
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        correlation_id = f"hash:{digest}"

    return f"{key_prefix}:{task_name}:{correlation_id}"


def idempotent_task(
    ttl: int = IDEMPOTENCY_TTL_SECONDS, key_prefix: str = "idempotency"
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to enforce idempotency on Celery tasks.

    - Checks Redis for an existing idempotency key before execution.
    - Sets key with TTL before execution.
    - Deletes key ONLY on successful completion.
    - On failure, leaves the key (or allows retries within retry window).
    - Prevents duplicate execution within the TTL window.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            task_name = func.__name__
            key = generate_idempotency_key(task_name, args, kwargs, key_prefix)

            # Use sync Redis connection for sync celery task worker
            sync_redis = SyncRedis.from_url(settings.redis_url, decode_responses=True)
            try:
                # SETNX via set(key, "in_progress", nx=True, ex=ttl)
                was_set = sync_redis.set(key, "in_progress", nx=True, ex=ttl)
                if not was_set:
                    logger.warning(
                        f"Idempotent task '{task_name}' skipped duplicate execution for key '{key}'"
                    )
                    return None

                result = func(*args, **kwargs)
                # Delete key ONLY on successful completion
                sync_redis.delete(key)
                return result
            except Exception as exc:
                logger.error(
                    "Task '%s' failed with error: %s. Removing the in-progress "
                    "marker so a retry can execute.",
                    task_name,
                    exc,
                )
                sync_redis.delete(key)
                raise
            finally:
                sync_redis.close()  # type: ignore[no-untyped-call]

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            task_name = func.__name__
            key = generate_idempotency_key(task_name, args, kwargs, key_prefix)

            redis: AsyncRedis = get_redis()
            try:
                was_set = await redis.set(key, "in_progress", nx=True, ex=ttl)
                if not was_set:
                    logger.warning(
                        f"Idempotent task '{task_name}' skipped duplicate execution for key '{key}'"
                    )
                    return None

                result = await func(*args, **kwargs)
                await redis.delete(key)
                return result
            except Exception as exc:
                logger.error(
                    "Task '%s' failed with error: %s. Removing the in-progress "
                    "marker so a retry can execute.",
                    task_name,
                    exc,
                )
                await redis.delete(key)
                raise

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
