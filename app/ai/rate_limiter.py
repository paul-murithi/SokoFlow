"""Atomic per-shop analytics rate limiting."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from redis.asyncio import Redis

NAIROBI = ZoneInfo("Africa/Nairobi")
WINDOW_TTL_SECONDS = 172800
_ADMIT_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if not current then
  redis.call('SET', KEYS[1], 1, 'EX', ARGV[2])
  return 1
end
if tonumber(current) >= tonumber(ARGV[1]) then
  return 0
end
redis.call('INCR', KEYS[1])
return 1
"""


class RateLimitUnavailableError(RuntimeError):
    """Raised when Redis cannot provide a reliable admission decision."""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    reason: str | None = None


class AnalyticsRateLimiter:
    """Enforces one atomic fixed-window quota per trusted shop identifier."""

    def __init__(
        self,
        redis: Redis,
        quota: int,
        *,
        key_prefix: str = "analytics:rate_limit",
        now: datetime | None = None,
    ) -> None:
        if quota < 1:
            raise ValueError("Analytics quota must be positive.")
        self.redis = redis
        self.quota = quota
        self.key_prefix = key_prefix
        self._now = now

    def key_for(self, shop_id: str) -> str:
        date = (self._now or datetime.now(NAIROBI)).astimezone(NAIROBI).date()
        return f"{self.key_prefix}:{shop_id}:{date.isoformat()}"

    async def admit(self, shop_id: str) -> RateLimitDecision:
        key = self.key_for(shop_id)
        try:
            result = await cast(
                Awaitable[Any],
                self.redis.eval(
                    _ADMIT_SCRIPT,
                    1,
                    key,
                    str(self.quota),
                    str(WINDOW_TTL_SECONDS),
                ),
            )
        except Exception as exc:
            raise RateLimitUnavailableError(
                "Analytics rate-limit infrastructure is unavailable."
            ) from exc

        if int(result) == 1:
            return RateLimitDecision(allowed=True)
        return RateLimitDecision(allowed=False, reason="daily_quota_exhausted")
