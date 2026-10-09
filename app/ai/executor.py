"""ToolExecutor Component — Deterministic Tool Execution Boundary.

Safely converts a model-proposed tool call into a validated, deterministic backend execution.
- Resolves requested tool via ToolRegistry (single source of truth).
- Rejects unregistered tools without guessing or fuzzy matching.
- Validates raw arguments against registered Pydantic input schemas prior to handler invocation.
- Invokes registered tool handler with trusted shop_id context.
- Wraps execution outcomes (success/failure) in a ToolExecutionResult envelope.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts.execution import ToolExecutionError, ToolExecutionResult
from app.ai.errors import (
    DomainValidationError,
    InfrastructureError,
    SchemaValidationError,
    ToolNotFoundError,
)
from app.ai.registry import ToolRegistry, default_registry
from app.ai.validator import ToolValidator

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Safely executes model-proposed tool calls against SokoFlow's internal service layer."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or default_registry

    async def execute(
        self,
        tool_name: str,
        raw_args: dict[str, Any],
        shop_id: UUID,
        db: AsyncSession,
    ) -> ToolExecutionResult:
        """Executes a proposed tool call deterministically.

        1. Tool Resolution: Looks up requested tool in Registry. Rejects if unknown.
        2. Structural Validation: Validates raw arguments against Pydantic input schema.
        3. Handler Invocation: Calls bound service handler with trusted shop_id context.
        4. Result Enveloping: Returns ToolExecutionResult(success/failure).
        """
        # Tool Resolution
        try:
            tool = self.registry.get_tool(tool_name)
        except ToolNotFoundError as exc:
            logger.warning("ToolExecutor rejected unknown tool request: '%s'", tool_name)
            return ToolExecutionResult(
                status="failure",
                tool=tool_name,
                error=ToolExecutionError(
                    error_type="ToolNotFoundError",
                    message=exc.message,
                    details={"tool_name": tool_name},
                ),
            )

        # Structural Validation
        try:
            validated_input = ToolValidator.validate_schema(tool.input_model, raw_args)
            ToolValidator.validate_domain(validated_input)
        except SchemaValidationError as exc:
            logger.warning(
                "ToolExecutor structural schema validation failed for tool '%s': %s",
                tool_name,
                exc.message,
            )
            return ToolExecutionResult(
                status="failure",
                tool=tool_name,
                error=ToolExecutionError(
                    error_type="SchemaValidationError",
                    message=exc.message,
                    details={"validation_errors": exc.errors},
                ),
            )
        except DomainValidationError as exc:
            logger.warning(
                "ToolExecutor domain validation failed at schema stage for tool '%s': %s",
                tool_name,
                exc.message,
            )
            return ToolExecutionResult(
                status="failure",
                tool=tool_name,
                error=ToolExecutionError(
                    error_type=type(exc).__name__,
                    message=exc.message,
                ),
            )

        # Handler Execution
        try:
            domain_result = await tool.handler(shop_id, validated_input, db)
            logger.info(
                "ToolExecutor successfully executed tool '%s' for shop %s", tool_name, shop_id
            )
            return ToolExecutionResult(
                status="success",
                tool=tool_name,
                data=domain_result,
            )
        except DomainValidationError as exc:
            logger.warning(
                "ToolExecutor domain execution error for tool '%s': %s", tool_name, exc.message
            )
            return ToolExecutionResult(
                status="failure",
                tool=tool_name,
                error=ToolExecutionError(
                    error_type=type(exc).__name__,
                    message=exc.message,
                ),
            )
        except InfrastructureError as exc:
            logger.error(
                "ToolExecutor infrastructure error for tool '%s': %s", tool_name, exc.message
            )
            return ToolExecutionResult(
                status="failure",
                tool=tool_name,
                error=ToolExecutionError(
                    error_type="InfrastructureError",
                    message=exc.message,
                ),
            )
        except Exception as exc:
            logger.exception(
                "ToolExecutor unexpected error during handler execution of '%s': %s",
                tool_name,
                exc,
            )
            return ToolExecutionResult(
                status="failure",
                tool=tool_name,
                error=ToolExecutionError(
                    error_type=type(exc).__name__,
                    message=str(exc),
                ),
            )
