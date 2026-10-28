"""Analytics Flow Component.

Adapts between the FSM conversation lifecycle and the Analytics Orchestrator.
- Translates inbound message and session context into an Orchestrator request.
- Invokes AnalyticsFormatter to turn typed Outcomes into presentation contracts.
- Updates session state, error counts, and prior/pending call contexts.
- Implements the disambiguation selection handler for SessionState.ANALYTICS_PRODUCT_SELECTION.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts.outcome import AnalyticsOutcome, OutcomeType
from app.ai.formatter import AnalyticsFormatter
from app.ai.orchestrator import AnalyticsOrchestrator
from app.core.config import settings
from app.fsm.models import (
    FSMResult,
    MessageKey,
    PendingCallContext,
    PriorCallContext,
    SessionState,
    UserSession,
)
from app.fsm.primitives import FSMPrimitives
from app.fsm.routing_policy import AnalyticsRoutingPolicy

logger = logging.getLogger(__name__)


class AnalyticsFlow(FSMPrimitives):
    """Conversation flow adapter for SokoFlow AI natural-language analytics."""

    MAX_ERROR_ATTEMPTS = settings.max_fsm_errors

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        orchestrator: AnalyticsOrchestrator | None = None,
        formatter: AnalyticsFormatter | None = None,
        routing_policy: AnalyticsRoutingPolicy | None = None,
    ) -> None:
        self.db_session = db_session
        self.orchestrator = orchestrator or AnalyticsOrchestrator()
        self.formatter = formatter or AnalyticsFormatter()
        self.routing_policy = routing_policy or AnalyticsRoutingPolicy()

    async def handle_query(self, session: UserSession, message_text: str) -> FSMResult:
        """Processes an analytics question from IDLE state."""
        previous_state = session.state

        async with self._get_db_session(db_session=self.db_session) as db:
            shop_id = await self.get_shop_id(db=db, sender=session.phone)
            session.context.shop_id = shop_id

            prior_context = (
                session.context.last_analytics_call
                if self.routing_policy.has_fresh_context(session)
                else None
            )

            outcome = await self.orchestrator.run(
                message_text=message_text,
                shop_id=shop_id,
                db=db,
                prior_context=prior_context,
            )

        match outcome.outcome_type:
            case OutcomeType.NEEDS_SELECTION:
                # Park session in ANALYTICS_PRODUCT_SELECTION
                self._transition(session, SessionState.ANALYTICS_PRODUCT_SELECTION)
                session.context.product_candidates = outcome.candidates
                session.context.pending_analytics_call = PendingCallContext(
                    tool_name=outcome.tool or "get_stock_level",
                    arguments=(
                        outcome.pending_call.get("arguments", {}) if outcome.pending_call else {}
                    ),
                    candidates=outcome.candidates,
                )
                session.context.error_count = 0
                message_key, message_params = self.formatter.format_outcome(outcome)
                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    message_key=message_key,
                    message_params=message_params,
                )

            case OutcomeType.ANSWERED | OutcomeType.ANSWERED_EMPTY:
                # Stay in IDLE, reset error count, record last call context
                session.context.error_count = 0
                if outcome.call:
                    session.context.last_analytics_call = PriorCallContext(
                        tool_name=outcome.call.get("name", outcome.tool or ""),
                        arguments=outcome.call.get("arguments", {}),
                    )
                message_key, message_params = self.formatter.format_outcome(outcome)
                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    message_key=message_key,
                    message_params=message_params,
                )

            case _:
                # Neutral non-execution (zero tool calls) or technical/domain failures:
                # Retain previous successful context, no incrementing error count
                message_key, message_params = self.formatter.format_outcome(outcome)
                return self._build_result(
                    previous_state=previous_state,
                    session=session,
                    message_key=message_key,
                    message_params=message_params,
                )

    async def handle_product_selection(self, session: UserSession, message_text: str) -> FSMResult:
        """Handles a disambiguation choice when parked in ANALYTICS_PRODUCT_SELECTION."""
        previous_state = session.state
        selected_product = self._resolve_product_choice(session, message_text)

        pending = session.context.pending_analytics_call
        if not pending:
            self._transition(session, SessionState.IDLE)
            self._clear_context_preserving_history(session)
            return self._build_result(
                previous_state=previous_state,
                session=session,
                message_key=MessageKey.SESSION_CONTEXT_LOST,
            )

        tool_name = pending.tool_name
        raw_args = dict(pending.arguments)
        raw_args["product_id"] = str(selected_product.id)
        raw_args["product_name"] = selected_product.name

        async with self._get_db_session(db_session=self.db_session) as db:
            shop_id = await self.get_shop_id(db=db, sender=session.phone)
            result = await self.orchestrator.executor.execute(
                tool_name=tool_name,
                raw_args=raw_args,
                shop_id=shop_id,
                db=db,
            )

        if result.is_success:
            arguments = result.validated_arguments or raw_args
            call_info = {
                "name": tool_name,
                "arguments": arguments,
            }
            if AnalyticsOrchestrator.is_result_empty(tool_name, result.data):
                outcome = AnalyticsOutcome.answered_empty(
                    tool=tool_name,
                    data=result.data,
                    call=call_info,
                )
            else:
                outcome = AnalyticsOutcome.answered(
                    tool=tool_name,
                    data=result.data,
                    call=call_info,
                )
            session.context.last_analytics_call = PriorCallContext(
                tool_name=tool_name,
                arguments=arguments,
            )
        else:
            error = result.error
            if error and error.error_type == "InfrastructureError":
                outcome = AnalyticsOutcome.infrastructure_failure(error.message)
            else:
                outcome = AnalyticsOutcome.domain_failure(
                    tool=tool_name,
                    error_type=error.error_type if error else "ExecutionFailure",
                    message=error.message if error else "Failed to execute tool",
                )

        session.context.pending_analytics_call = None
        session.context.product_candidates = []
        self._transition(session, SessionState.IDLE)

        message_key, message_params = self.formatter.format_outcome(outcome)
        return self._build_result(
            previous_state=previous_state,
            session=session,
            message_key=message_key,
            message_params=message_params,
        )
