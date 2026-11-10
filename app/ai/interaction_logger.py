"""Best-effort persistence for bounded analytics interaction diagnostics."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts.llm import LLMResponse
from app.ai.contracts.outcome import AnalyticsOutcome, OutcomeType
from app.models.analytics_interaction import AnalyticsInteraction

logger = logging.getLogger(__name__)


@dataclass
class InteractionTrace:
    """In-memory bounded trace accumulated during one logical interaction."""

    shop_id: UUID
    raw_query: str
    started_at: float = field(default_factory=time.perf_counter)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    usage_seen: bool = False
    usage_complete: bool = True
    actual_cost_usd: float | None = None
    provider: str | None = None
    model: str | None = None

    def record_provider_attempt(
        self,
        response: LLMResponse,
        *,
        proposed_tool: str | None = None,
        proposed_arguments: dict[str, Any] | None = None,
        result: str | None = None,
        repair: bool = False,
    ) -> None:
        if response.prompt_tokens is not None:
            self.input_tokens += response.prompt_tokens
            self.usage_seen = True
        else:
            self.usage_complete = False
        if response.completion_tokens is not None:
            self.output_tokens += response.completion_tokens
            self.usage_seen = True
        else:
            self.usage_complete = False
        if response.cost_usd is not None:
            self.actual_cost_usd = (self.actual_cost_usd or 0.0) + response.cost_usd
        self.attempts.append(
            {
                "tool_name": proposed_tool,
                "arguments": proposed_arguments,
                "result": result,
                "repair": repair,
                "latency_ms": None,
            }
        )

    def record_failure(self, message: str, *, repair: bool = False) -> None:
        self.attempts.append({"result": "failure", "failure": message, "repair": repair})


class InteractionLogger:
    """Persists one finalized record without affecting the business outcome."""

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("Interaction log pseudonymization secret must not be empty.")
        self._secret = secret.encode()

    def shop_ref(self, shop_id: UUID) -> str:
        return hmac.new(self._secret, str(shop_id).encode(), hashlib.sha256).hexdigest()

    async def finalize(
        self,
        trace: InteractionTrace,
        outcome: AnalyticsOutcome,
        db: AsyncSession,
        *,
        guardrail_decision: str = "allowed",
        guardrail_reason: str | None = None,
    ) -> None:
        outcome_name = (
            "success"
            if outcome.outcome_type is OutcomeType.ANSWERED
            else "empty_result"
            if outcome.outcome_type is OutcomeType.ANSWERED_EMPTY
            else "failure"
            if outcome.outcome_type is not OutcomeType.GUARDRAIL_REJECTED
            else "guardrail_rejected"
        )
        usage_status = (
            "complete"
            if trace.usage_seen and trace.usage_complete
            else "partial"
            if trace.usage_seen
            else "unavailable"
        )
        record = AnalyticsInteraction(
            id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            shop_ref=self.shop_ref(trace.shop_id),
            raw_query=trace.raw_query,
            outcome=outcome_name,
            failure_category=(
                outcome.error_type or outcome.outcome_type.value
                if outcome_name == "failure"
                else None
            ),
            tool_name=outcome.tool,
            selected_arguments=(outcome.call or {}).get("arguments"),
            provider=trace.provider,
            model=trace.model,
            attempt_count=len(trace.attempts),
            repair_count=sum(1 for attempt in trace.attempts if attempt.get("repair")),
            total_latency_ms=(time.perf_counter() - trace.started_at) * 1000,
            input_tokens=trace.input_tokens if trace.usage_seen else None,
            output_tokens=trace.output_tokens if trace.usage_seen else None,
            estimated_cost=None,
            actual_cost=trace.actual_cost_usd,
            usage_status=usage_status,
            guardrail_decision=guardrail_decision,
            guardrail_reason=guardrail_reason,
            attempts=trace.attempts,
        )
        try:
            db.add(record)
            await db.flush()
        except Exception:
            logger.exception("Failed to persist analytics interaction %s", record.id)
            try:
                await db.rollback()
            except Exception:
                logger.exception(
                    "Failed to recover database session after interaction logging error"
                )
