from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.fsm.models import PriorCallContext, SessionContext, SessionState, UserSession
from app.fsm.routing_policy import AnalyticsRoutingPolicy


def test_routing_policy_disabled():
    policy = AnalyticsRoutingPolicy(enabled=False)
    session = UserSession(phone="+254700111222", state=SessionState.IDLE, context=SessionContext())

    assert policy.can_route(session, "How are sales today?") is False


def test_routing_policy_no_provider_api_keys(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "openrouter_api_key", None)

    policy = AnalyticsRoutingPolicy(enabled=True)
    session = UserSession(phone="+254700111222", state=SessionState.IDLE, context=SessionContext())

    assert policy.can_route(session, "How are sales today?") is False


def test_routing_policy_message_length_bounds(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test_key")

    policy = AnalyticsRoutingPolicy(enabled=True)
    session = UserSession(phone="+254700111222", state=SessionState.IDLE, context=SessionContext())

    # Too short (< 2 chars after strip)
    assert policy.can_route(session, "") is False
    assert policy.can_route(session, "a") is False
    assert policy.can_route(session, "   ") is False

    # Within bounds (>= 2 and <= 500)
    assert policy.can_route(session, "hi") is True

    # Too long (> 500 chars)
    long_msg = "x" * 501
    assert policy.can_route(session, long_msg) is False


def test_routing_policy_bare_number_without_context(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test_key")

    policy = AnalyticsRoutingPolicy(enabled=True)
    session = UserSession(phone="+254700111222", state=SessionState.IDLE, context=SessionContext())

    # Bare number without previous analytics call
    assert policy.can_route(session, "1") is False
    assert policy.can_route(session, "42") is False


def test_routing_policy_bare_number_with_fresh_context(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test_key")

    policy = AnalyticsRoutingPolicy(enabled=True, follow_up_ttl_seconds=600)
    recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)
    prior = PriorCallContext(
        tool_name="get_sales_summary",
        arguments={"period": "today"},
        timestamp=recent_time,
    )
    session = UserSession(
        phone="+254700111222",
        state=SessionState.IDLE,
        context=SessionContext(last_analytics_call=prior),
    )

    # Bare number with fresh context is allowed for follow-up (choice or follow-up)
    assert policy.can_route(session, "1") is True


def test_routing_policy_expired_context(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test_key")

    policy = AnalyticsRoutingPolicy(enabled=True, follow_up_ttl_seconds=300)
    old_time = datetime.now(timezone.utc) - timedelta(seconds=301)
    prior = PriorCallContext(
        tool_name="get_sales_summary",
        arguments={"period": "today"},
        timestamp=old_time,
    )
    session = UserSession(
        phone="+254700111222",
        state=SessionState.IDLE,
        context=SessionContext(last_analytics_call=prior),
    )

    assert policy.has_fresh_context(session) is False
    # Since context is expired, bare number is rejected
    assert policy.can_route(session, "1") is False
    # Normal query is still accepted
    assert policy.can_route(session, "How are sales today?") is True


def test_routing_policy_valid_query(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test_key")

    policy = AnalyticsRoutingPolicy(enabled=True)
    session = UserSession(phone="+254700111222", state=SessionState.IDLE, context=SessionContext())

    assert policy.can_route(session, "What are my top products?") is True
    assert policy.can_route(session, "How much stock of milk do I have?") is True
