from uuid import uuid4

from app.ai.errors import (
    InfrastructureError,
    InvalidDateRangeError,
    ProductNotFoundError,
    ProductResolutionFailedError,
    SchemaValidationError,
    ToolNotFoundError,
)
from app.ai.retry import BoundedRetryPolicy, is_llm_retryable_error


def test_is_llm_retryable_error():
    assert is_llm_retryable_error(ToolNotFoundError("invalid_tool")) is True
    assert is_llm_retryable_error(SchemaValidationError("invalid schema")) is True

    assert is_llm_retryable_error(InvalidDateRangeError()) is False
    assert is_llm_retryable_error(ProductNotFoundError(uuid4())) is False
    assert is_llm_retryable_error(ProductResolutionFailedError("bread")) is False
    assert is_llm_retryable_error(InfrastructureError("db connection failed")) is False
    assert is_llm_retryable_error(ValueError("generic error")) is False


def test_bounded_retry_policy_can_retry():
    err = SchemaValidationError("invalid args")

    # Attempt 0 -> can retry
    assert BoundedRetryPolicy.can_retry(0, err) is True

    # Attempt 1 -> MAX_RETRIES reached -> cannot retry
    assert BoundedRetryPolicy.can_retry(1, err) is False
    assert BoundedRetryPolicy.can_retry(2, err) is False

    # Domain error -> attempt 0 cannot retry
    domain_err = InvalidDateRangeError()
    assert BoundedRetryPolicy.can_retry(0, domain_err) is False


def test_format_llm_feedback():
    tool_err = ToolNotFoundError("get_sales_summry")
    msg = BoundedRetryPolicy.format_llm_feedback(tool_err)
    assert "Tool 'get_sales_summry' does not exist" in msg

    schema_err = SchemaValidationError("invalid enum")
    msg_schema = BoundedRetryPolicy.format_llm_feedback(schema_err)
    assert "Tool Argument Error" in msg_schema
