"""Tool Validator Pipeline.

Implements a multi-stage validation pipeline:
1. Tool existence (handled by ToolRegistry)
2. Schema validation (Pydantic model validation with extra="forbid")
3. Domain validation (Business rules, such as date range checks)
"""

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.errors import InvalidDateRangeError, SchemaValidationError

T = TypeVar("T", bound=BaseModel)


class ToolValidator:
    """Validates raw LLM arguments against Pydantic schemas and domain rules."""

    @staticmethod
    def validate_schema(input_model: type[T], raw_args: dict[str, Any]) -> T:
        """Validates raw arguments against input Pydantic schema.

        Rejects unexpected arguments (e.g. shop_id injection attempts).
        Raises SchemaValidationError on structural failure.
        """
        if "shop_id" in raw_args:
            raise SchemaValidationError(
                "Argument 'shop_id' is prohibited in AI tool calls. "
                "Shop scope is trusted backend context."
            )

        try:
            validated_input = input_model.model_validate(raw_args)
        except InvalidDateRangeError:
            # Domain validation errors are raised to be handled by the caller.
            raise
        except ValidationError as exc:
            error_details = []
            for err in exc.errors():
                loc = " -> ".join(str(p) for p in err["loc"])
                msg = err["msg"]
                error_details.append({"loc": loc, "message": msg, "type": err["type"]})
            raise SchemaValidationError(
                f"Schema validation failed for {input_model.__name__}: {exc}",
                errors=error_details,
            ) from exc

        return validated_input

    @staticmethod
    def validate_domain(validated_input: BaseModel) -> None:
        """Enforces domain-level business rules on validated input models."""
        # Period date validation is automatically triggered in the DateRange validator,
        # Left as a placeholder for future domain validation logic.
        pass
