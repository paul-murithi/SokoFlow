"""Analytics Routing Policy.

Evaluates whether an incoming message with no regex match (Intent.UNKNOWN)
should be escalated to the analytics model interaction.
Acts as a gatekeeper (not a classifier), deciding if spending a model call is acceptable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.fsm.models import UserSession

logger = logging.getLogger(__name__)


class AnalyticsRoutingPolicy:
    """Gatekeeper policy determining whether an unknown message may enter Analytics."""

    MIN_MESSAGE_LENGTH: int = 2
    MAX_MESSAGE_LENGTH: int = 500

    def __init__(
        self,
        enabled: bool | None = None,
        follow_up_ttl_seconds: int | None = None,
    ) -> None:
        self.enabled = (
            enabled if enabled is not None else getattr(settings, "analytics_enabled", True)
        )
        self.follow_up_ttl_seconds = (
            follow_up_ttl_seconds
            if follow_up_ttl_seconds is not None
            else getattr(settings, "analytics_follow_up_ttl_seconds", 600)
        )

    def can_route(self, session: UserSession, message_text: str) -> bool:
        """Returns True if the message should be escalated to the analytics orchestrator."""
        # TODO: Feature flag for per-shop enablement is not implemented yet
        if not self.enabled:
            logger.debug("Analytics routing disabled via configuration.")
            return False

        # Provider credentials check
        if not (settings.groq_api_key or settings.openrouter_api_key):
            logger.warning("Analytics routing declined: No LLM provider API key configured.")
            return False

        # Message shape validation
        cleaned = message_text.strip()
        min_len = 1 if self.has_fresh_context(session) else self.MIN_MESSAGE_LENGTH
        if len(cleaned) < min_len or len(cleaned) > self.MAX_MESSAGE_LENGTH:
            logger.debug(
                "Analytics routing declined: Message length %d outside [%d, %d].",
                len(cleaned),
                min_len,
                self.MAX_MESSAGE_LENGTH,
            )
            return False

        # A bare number without fresh follow-up context is not analytics
        if cleaned.isdigit() and not self.has_fresh_context(session):
            logger.debug("Analytics routing declined: Bare number without fresh follow-up context.")
            return False

        return True

    def has_fresh_context(self, session: UserSession) -> bool:
        """Returns True if the session contains an unexpired last_analytics_call context."""
        ctx = session.context.last_analytics_call
        if ctx is None:
            return False

        now = datetime.now(timezone.utc)
        elapsed = (now - ctx.timestamp).total_seconds()
        return elapsed <= self.follow_up_ttl_seconds
