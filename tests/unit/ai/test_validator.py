from uuid import uuid4

import pytest

from app.ai.contracts.tools import GetSalesSummaryInput, GetStockLevelInput
from app.ai.errors import SchemaValidationError
from app.ai.validator import ToolValidator


def test_validate_schema_success():
    raw_args = {
        "period": {
            "period_type": "relative",
            "relative_period": "month",
        }
    }
    validated = ToolValidator.validate_schema(GetSalesSummaryInput, raw_args)
    assert isinstance(validated, GetSalesSummaryInput)
    assert validated.period.relative_period == "month"


def test_validate_schema_rejects_shop_id_injection():
    raw_args = {
        "product_id": str(uuid4()),
        "shop_id": str(uuid4()),
    }
    with pytest.raises(SchemaValidationError, match="prohibited in AI tool calls"):
        ToolValidator.validate_schema(GetStockLevelInput, raw_args)


def test_validate_schema_rejects_non_dict_input():
    with pytest.raises(SchemaValidationError, match="Expected tool arguments to be a dictionary"):
        ToolValidator.validate_schema(GetStockLevelInput, "not a dict")


def test_validate_schema_invalid_enum():
    raw_args = {
        "period": {
            "period_type": "relative",
            "relative_period": "banana",
        }
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        ToolValidator.validate_schema(GetSalesSummaryInput, raw_args)
    assert len(exc_info.value.errors) > 0
