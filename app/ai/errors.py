"""AI Layer Error Taxonomy.

Categorizes errors into LLM-retryable (ToolNotFound, SchemaValidation) vs
non-LLM-retryable (DomainValidation, Infrastructure).
"""

from typing import Any
from uuid import UUID


class AIToolError(Exception):
    """Base exception for AI Tool operations."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ToolNotFoundError(AIToolError):
    """Raised when the requested tool name is not registered in the ToolRegistry."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' is not registered in the AI tool surface.")


class SchemaValidationError(AIToolError):
    """Raised when the LLM provided arguments that fail structural schema validation."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class DomainValidationError(AIToolError):
    """Base exception for domain and business rule validation failures.

    These represent validly formatted requests that violate business logic.
    They MUST NOT trigger LLM retries.
    """


class InvalidDateRangeError(DomainValidationError):
    """Raised when date range boundaries violate reporting rules."""

    def __init__(self, message: str = "Start date must be strictly before end date.") -> None:
        super().__init__(message)


class ProductNotFoundError(DomainValidationError):
    """Raised when a specific product identity does not exist for the shop."""

    def __init__(self, product_id: UUID | str) -> None:
        self.product_id = product_id
        super().__init__(f"Product with ID '{product_id}' was not found for this shop.")


class ProductResolutionFailedError(DomainValidationError):
    """Raised when fuzzy product matching cannot establish a confident product match."""

    def __init__(self, search_term: str, reason: str = "No matching product found.") -> None:
        self.search_term = search_term
        self.reason = reason
        super().__init__(f"Could not resolve product '{search_term}': {reason}")


class UnsupportedOperationError(DomainValidationError):
    """Raised when a requested feature or parameter combination is not supported."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"Operation '{operation}' is not supported by the AI tool surface.")


class InfrastructureError(AIToolError):
    """Raised when an underlying database, Redis, or service error occurs during execution."""

    def __init__(self, message: str, original_exception: Exception | None = None) -> None:
        super().__init__(message)
        self.original_exception = original_exception


class LLMProviderError(AIToolError):
    """Base exception for LLM provider boundary failures."""

    def __init__(self, message: str, original_exception: Exception | None = None) -> None:
        super().__init__(message)
        self.original_exception = original_exception


class LLMProviderTimeoutError(LLMProviderError):
    """Raised when request to LLM provider times out."""


class LLMProviderUnavailableError(LLMProviderError):
    """Raised when LLM provider service is unavailable (5xx status)."""


class LLMProviderAPIError(LLMProviderError):
    """Raised when LLM provider returns a client error (4xx status)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        super().__init__(message, original_exception=original_exception)
        self.status_code = status_code


class LLMResponseFormatError(LLMProviderError):
    """Raised when LLM provider response structure cannot be interpreted."""
