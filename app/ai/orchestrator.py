"""Analytics Orchestrator Component.

Coordinates natural-language interpretation, model response inspection, deterministic
tool execution, and bounded retries. Produces a typed AnalyticsOutcome.
Must be runnable without session, Redis, locale, or WhatsApp dependencies.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts.llm import LLMMessage
from app.ai.contracts.outcome import AnalyticsOutcome
from app.ai.errors import (
    LLMProviderAPIError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
    LLMResponseFormatError,
)
from app.ai.executor import ToolExecutor
from app.ai.llm_client import LLMClient
from app.ai.registry import ToolRegistry, default_registry
from app.fsm.models import PriorCallContext, ScoredProductMatch

logger = logging.getLogger(__name__)

DEFAULT_ACTIVE_TOOLS = (
    "get_sales_summary",
    "get_stock_level",
    "get_top_products",
)


class AnalyticsOrchestrator:
    """Coordinates one analytics request from question to typed Outcome."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        executor: ToolExecutor | None = None,
        registry: ToolRegistry | None = None,
        active_tools: tuple[str, ...] | None = None,
    ) -> None:
        self.registry = registry or default_registry
        self.llm_client = llm_client or LLMClient()
        self.executor = executor or ToolExecutor(registry=self.registry)
        self.active_tools = active_tools if active_tools is not None else DEFAULT_ACTIVE_TOOLS

    async def run(
        self,
        message_text: str,
        shop_id: UUID,
        db: AsyncSession,
        prior_context: PriorCallContext | None = None,
    ) -> AnalyticsOutcome:
        """Executes the analytics query orchestration loop and returns a typed AnalyticsOutcome."""
        messages: list[LLMMessage] = []

        if prior_context:
            args_str = json.dumps(prior_context.arguments)
            messages.append(
                LLMMessage(
                    role="assistant",
                    content=(
                        f"Previous tool executed: {prior_context.tool_name} "
                        f"with arguments {args_str}"
                    ),
                )
            )

        messages.append(LLMMessage(role="user", content=message_text))

        all_tools = self.registry.get_openai_tools()
        tools = [
            t for t in all_tools if t.get("function", {}).get("name") in self.active_tools
        ]

        # Bounded retry: at most 1 retry for LLM response or tool argument validation errors
        for attempt in range(2):
            try:
                response = await self.llm_client.generate(messages=messages, tools=tools)
            except (
                LLMProviderTimeoutError,
                LLMProviderUnavailableError,
                LLMProviderAPIError,
                LLMResponseFormatError,
            ) as exc:
                logger.warning("LLM provider error in orchestrator: %s", exc)
                return AnalyticsOutcome.provider_unavailable(str(exc))
            except Exception as exc:
                logger.exception("Unexpected error calling LLM provider: %s", exc)
                return AnalyticsOutcome.provider_unavailable(str(exc))

            if not response.has_tool_calls:
                return AnalyticsOutcome.no_analytics_intent()

            if len(response.tool_calls) > 1:
                if attempt == 0:
                    messages.append(LLMMessage(role="assistant", content=None))
                    messages.append(
                        LLMMessage(
                            role="user",
                            content=(
                                "Please propose only ONE analytics tool call for this question."
                            ),
                        )
                    )
                    continue
                return AnalyticsOutcome.invalid_proposal("Multiple tool calls proposed.")

            tool_call = response.primary_tool_call
            assert tool_call is not None

            if tool_call.name not in self.active_tools:
                if attempt == 0:
                    messages.append(LLMMessage(role="assistant", content=None))
                    messages.append(
                        LLMMessage(
                            role="user",
                            content=(
                                f"Tool '{tool_call.name}' is not recognized. "
                                f"Please select from: {', '.join(self.active_tools)}."
                            ),
                        )
                    )
                    continue
                return AnalyticsOutcome.invalid_proposal(
                    f"Unknown tool '{tool_call.name}'.", tool=tool_call.name
                )

            # Invoke ToolExecutor
            result = await self.executor.execute(
                tool_name=tool_call.name,
                raw_args=tool_call.arguments,
                shop_id=shop_id,
                db=db,
            )

            if result.is_success:
                call_info = {"name": tool_call.name, "arguments": tool_call.arguments}
                if self._is_result_empty(tool_call.name, result.data):
                    return AnalyticsOutcome.answered_empty(
                        tool=tool_call.name, data=result.data, call=call_info
                    )
                return AnalyticsOutcome.answered(
                    tool=tool_call.name, data=result.data, call=call_info
                )

            # Failure handling
            error = result.error
            assert error is not None

            if error.error_type == "SchemaValidationError":
                if attempt == 0:
                    messages.append(LLMMessage(role="assistant", content=None))
                    messages.append(
                        LLMMessage(
                            role="user",
                            content=(
                                f"Tool argument schema error: {error.message}. "
                                "Please adjust parameters according to the tool's JSON schema."
                            ),
                        )
                    )
                    continue
                return AnalyticsOutcome.argument_validation_failed(
                    tool=tool_call.name,
                    message=error.message,
                    details=error.details,
                )

            if error.error_type == "ProductAmbiguousError":
                candidates_data = (
                    error.details.get("candidates", []) if error.details else []
                )
                candidates = [
                    ScoredProductMatch.model_validate(c) if isinstance(c, dict) else c
                    for c in candidates_data
                ]
                pending_call = {
                    "tool_name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
                return AnalyticsOutcome.needs_selection(
                    candidates=candidates,
                    pending_call=pending_call,
                    tool=tool_call.name,
                )

            if error.error_type == "InfrastructureError":
                return AnalyticsOutcome.provider_unavailable(error.message)

            return AnalyticsOutcome.domain_failure(
                tool=tool_call.name,
                error_type=error.error_type,
                message=error.message,
                details=error.details,
            )

        return AnalyticsOutcome.invalid_proposal("Exhausted retry attempts.")

    @staticmethod
    def _is_result_empty(tool_name: str, data: Any) -> bool:
        if tool_name == "get_sales_summary":
            rev = getattr(data, "total_revenue", 0)
            tx = getattr(data, "transaction_count", 0)
            return rev == 0 and tx == 0
        if tool_name == "get_top_products":
            units = getattr(data, "units", None)
            revenue = getattr(data, "revenue", None)
            return not units and not revenue
        return False
