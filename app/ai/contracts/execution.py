"""SokoFlow Tool Execution Envelope Contracts.

Defines the ToolExecutionResult envelope and structured ToolExecutionError models
used by ToolExecutor to represent execution outcomes.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolExecutionError(BaseModel):
    """Structured error details for failed tool execution."""

    model_config = ConfigDict(extra="forbid")

    error_type: str = Field(
        ...,
        description=(
            "Error category name (e.g. 'ToolNotFoundError', "
            "'SchemaValidationError', 'DomainValidationError')."
        ),
    )
    message: str = Field(..., description="Human-readable error description.")
    details: dict[str, Any] | None = Field(
        default=None, description="Optional extra error metadata or validation field errors."
    )


class ToolExecutionResult(BaseModel):
    """Envelope returned by ToolExecutor representing the execution outcome."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failure"] = Field(
        ..., description="Execution status ('success' or 'failure')."
    )
    tool: str = Field(..., description="Name of the target tool.")
    data: Any | None = Field(
        default=None, description="Structured domain output payload on success."
    )
    error: ToolExecutionError | None = Field(
        default=None, description="Structured error details on failure."
    )

    @property
    def is_success(self) -> bool:
        """Returns True if execution succeeded."""
        return self.status == "success"

    @property
    def is_failure(self) -> bool:
        """Returns True if execution failed."""
        return self.status == "failure"
