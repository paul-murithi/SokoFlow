"""AI Failure Classification and Retry Policy.

Enforces principle to Retry AI mistakes, not retry domain truth.
- Tool selection and schema failures are retryable once.
- Domain validation failures & infrastructure errors -> Non-retryable via LLM.
"""

import logging

from app.ai.errors import (
    DomainValidationError,
    InfrastructureError,
    SchemaValidationError,
    ToolNotFoundError,
)

logger = logging.getLogger(__name__)


def is_llm_retryable_error(error: Exception) -> bool:
    """Returns True if the exception was caused by an LLM tool call mistake that is eligible

    for a bounded LLM retry.
    """
    if isinstance(error, (ToolNotFoundError, SchemaValidationError)):
        return True
    if isinstance(error, (DomainValidationError, InfrastructureError)):
        return False
    return False


class BoundedRetryPolicy:
    """Orchestrates bounded retry logic for LLM tool call failures.

    Strictly enforces MAX_RETRIES = 1.
    """

    MAX_RETRIES: int = 1 #TODO: Make this configurable via settings

    @classmethod
    def can_retry(cls, current_attempt: int, error: Exception) -> bool:
        """Determines if a retry should be attempted given the current attempt count and error."""
        if current_attempt >= cls.MAX_RETRIES:
            logger.info("Maximum LLM tool retry limit (%d) reached.", cls.MAX_RETRIES)
            return False
        return is_llm_retryable_error(error)

    @classmethod
    def format_llm_feedback(cls, error: Exception) -> str:
        """Format error feedback into a clear prompt for a bounded LLM retry."""
        if isinstance(error, ToolNotFoundError):
            return (
                f"Tool Call Error: Tool '{error.tool_name}' does not exist. "
                "Please select a valid tool from the registered tool definitions."
            )
        if isinstance(error, SchemaValidationError):
            details = (
                "; ".join(e.get("message", "") for e in error.errors)
                if error.errors
                else error.message
            )
            return (
                "Tool Argument Error: The arguments provided were invalid: "
                f"{error.message}. "
                f"Details: {details}. Please adjust your call according to the tool's JSON schema."
            )
        return f"Tool Execution Error: {str(error)}"
