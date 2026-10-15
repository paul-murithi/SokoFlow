"""Typed Outcome Contract for SokoFlow AI Analytics Orchestration.

Defines the discriminated Outcome returned by AnalyticsOrchestrator to the conversation layer.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.fsm.models import ScoredProductMatch


class OutcomeType(StrEnum):
    """Categorized outcome types returned by the analytics orchestrator."""

    ANSWERED = "answered"
    ANSWERED_EMPTY = "answered_empty"
    NEEDS_SELECTION = "needs_selection"
    NO_ANALYTICS_INTENT = "no_analytics_intent"
    INVALID_PROPOSAL = "invalid_proposal"
    ARGUMENT_VALIDATION_FAILED = "argument_validation_failed"
    DOMAIN_FAILURE = "domain_failure"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class AnalyticsOutcome(BaseModel):
    """Discriminated outcome of an analytics question orchestration."""

    model_config = ConfigDict(extra="forbid")

    outcome_type: OutcomeType = Field(..., description="The categorized outcome type.")
    tool: str | None = Field(default=None, description="The tool that was proposed/executed.")
    data: Any | None = Field(
        default=None, description="Domain output model or data payload on successful execution."
    )
    call: dict[str, Any] | None = Field(
        default=None,
        description="The validated tool call (tool_name and arguments) producing this result.",
    )
    candidates: list[ScoredProductMatch] = Field(
        default_factory=list, description="Product candidate choices for NeedsSelection."
    )
    pending_call: dict[str, Any] | None = Field(
        default=None, description="Pending tool call to resume once selection is made."
    )
    error_type: str | None = Field(
        default=None, description="Category of error on failure (e.g. ProductNotFoundError)."
    )
    message: str | None = Field(
        default=None, description="Human-readable description of error or failure reason."
    )
    details: dict[str, Any] | None = Field(
        default=None, description="Additional structured error details."
    )

    @property
    def is_answered(self) -> bool:
        """Returns True if the request was answered with data or empty data."""
        return self.outcome_type in (OutcomeType.ANSWERED, OutcomeType.ANSWERED_EMPTY)

    @property
    def is_needs_selection(self) -> bool:
        """Returns True if user selection is required to disambiguate the request."""
        return self.outcome_type == OutcomeType.NEEDS_SELECTION

    @classmethod
    def answered(
        cls, tool: str, data: Any, call: dict[str, Any] | None = None
    ) -> "AnalyticsOutcome":
        return cls(outcome_type=OutcomeType.ANSWERED, tool=tool, data=data, call=call)

    @classmethod
    def answered_empty(
        cls, tool: str, data: Any, call: dict[str, Any] | None = None
    ) -> "AnalyticsOutcome":
        return cls(outcome_type=OutcomeType.ANSWERED_EMPTY, tool=tool, data=data, call=call)

    @classmethod
    def needs_selection(
        cls,
        candidates: list[ScoredProductMatch],
        pending_call: dict[str, Any] | None = None,
        tool: str | None = None,
    ) -> "AnalyticsOutcome":
        return cls(
            outcome_type=OutcomeType.NEEDS_SELECTION,
            tool=tool,
            candidates=candidates,
            pending_call=pending_call,
        )

    @classmethod
    def no_analytics_intent(cls) -> "AnalyticsOutcome":
        return cls(outcome_type=OutcomeType.NO_ANALYTICS_INTENT)

    @classmethod
    def invalid_proposal(cls, reason: str, tool: str | None = None) -> "AnalyticsOutcome":
        return cls(outcome_type=OutcomeType.INVALID_PROPOSAL, tool=tool, message=reason)

    @classmethod
    def argument_validation_failed(
        cls, tool: str, message: str, details: dict[str, Any] | None = None
    ) -> "AnalyticsOutcome":
        return cls(
            outcome_type=OutcomeType.ARGUMENT_VALIDATION_FAILED,
            tool=tool,
            message=message,
            details=details,
        )

    @classmethod
    def domain_failure(
        cls, tool: str, error_type: str, message: str, details: dict[str, Any] | None = None
    ) -> "AnalyticsOutcome":
        return cls(
            outcome_type=OutcomeType.DOMAIN_FAILURE,
            tool=tool,
            error_type=error_type,
            message=message,
            details=details,
        )

    @classmethod
    def provider_unavailable(cls, message: str) -> "AnalyticsOutcome":
        return cls(outcome_type=OutcomeType.PROVIDER_UNAVAILABLE, message=message)
