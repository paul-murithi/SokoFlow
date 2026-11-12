from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.rate_limiter import AnalyticsRateLimiter, RateLimitUnavailableError
from app.core.config import settings
from app.fsm.engine import FSMEngine
from app.fsm.models import MessageKey, SessionContext, SessionState, UserSession


def test_fsmengine_fails_when_rate_limiter_cannot_be_created(monkeypatch):
    """Production start‑up must abort if the rate‑limiter cannot be built.
    We simulate a bad Redis URL that causes the factory to raise.
    """
    monkeypatch.setattr(settings, "redis_url", "redis://invalid-host:6379/0")
    # The import inside FSMEngine will attempt to create a Redis client which
    # will raise a connection‑error when `AnalyticsRateLimiter.__init__` tries to
    # use it. The outer try/except in FSMEngine should convert that to a
    # RuntimeError.
    with pytest.raises(RuntimeError, match="Cannot create a functional AnalyticsRateLimiter"):
        FSMEngine(db_session=object())


@pytest.mark.asyncio
async def test_rate_limiter_unavailable_at_admit(monkeypatch):
    """When Redis is down during `admit`, the flow returns the guard‑rail
    rejection outcome (MessageKey.ANALYTICS_UNAVAILABLE).
    """
    # Build a mock limiter that raises RateLimitUnavailableError on admit().
    mock_limiter = MagicMock(spec=AnalyticsRateLimiter)
    mock_limiter.admit = AsyncMock(side_effect=RateLimitUnavailableError())

    engine = FSMEngine(
        db_session=object(),
        rate_limiter_factory=lambda: mock_limiter,
    )

    session = UserSession(
        phone="+254700000111",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    # The message should be routed to analytics (unknown intent) and then hit the limiter.
    result = await engine.process_message(session, "How many sales today?")

    assert result.message_key == MessageKey.ANALYTICS_UNAVAILABLE
    # No error count accumulation because the flow handled the failure.
    assert session.context.error_count == 0


@pytest.mark.asyncio
async def test_non_analytics_message_skips_rate_limiter(monkeypatch):
    """A non‑analytics intent never calls the limiter (verify with a spy)."""
    mock_limiter = MagicMock(spec=AnalyticsRateLimiter)
    mock_limiter.admit = AsyncMock()

    engine = FSMEngine(
        db_session=object(),
        rate_limiter_factory=lambda: mock_limiter,
    )

    session = UserSession(
        phone="+254700000222",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    result = await engine.process_message(session, "Add product Milk 1L 110")

    assert result.message_key == MessageKey.START_ADD_PRODUCT
    mock_limiter.admit.assert_not_called()


@pytest.mark.asyncio
async def test_multi_turn_follow_up_hits_rate_limiter(monkeypatch, redis_mock):
    """Both the initial query and a follow‑up should invoke `admit`.
    We use a real limiter backed by the test Redis fixture.
    """
    # Build a real limiter using the fixture's Redis client.
    limiter = AnalyticsRateLimiter(redis_mock, settings.analytics_daily_quota)

    engine = FSMEngine(
        db_session=object(),
        rate_limiter_factory=lambda: limiter,
    )

    session = UserSession(
        phone="+254700000333",
        state=SessionState.IDLE,
        context=SessionContext(),
    )

    # Turn 1 – primary analytics query.
    await engine.process_message(session, "Sales today?")

    # Spy on admit for the second turn.
    original_admit = limiter.admit
    admit_spy = AsyncMock(wraps=original_admit)
    limiter.admit = admit_spy

    # Turn 2 – follow‑up.
    await engine.process_message(session, "and yesterday?")

    assert admit_spy.call_count == 1
