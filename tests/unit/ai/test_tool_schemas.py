from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.contracts.period import PeriodType, RelativePeriod, ReportingPeriod
from app.ai.contracts.tools import (
    GetLowStockItemsInput,
    GetSalesSummaryInput,
    GetStockLevelInput,
    GetTopProductsInput,
    RankingDimension,
)


def test_sales_summary_input_valid():
    period = ReportingPeriod(period_type=PeriodType.RELATIVE, relative_period=RelativePeriod.DAY)
    inp = GetSalesSummaryInput(period=period)
    assert inp.period.relative_period == RelativePeriod.DAY


def test_sales_summary_input_rejects_extra_fields():
    period_dict = {"period_type": "relative", "relative_period": "day"}
    with pytest.raises(ValidationError):
        GetSalesSummaryInput.model_validate({"period": period_dict, "shop_id": str(uuid4())})


def test_top_products_input_optional_fields():
    period_dict = {"period_type": "relative", "relative_period": "month"}
    inp = GetTopProductsInput.model_validate(
        {"period": period_dict, "ranking_dimension": "units", "limit": 10}
    )
    assert inp.ranking_dimension == RankingDimension.UNITS
    assert inp.limit == 10


def test_stock_level_input_uuid_validation():
    valid_uuid = uuid4()
    inp = GetStockLevelInput(product_id=valid_uuid)
    assert inp.product_id == valid_uuid

    with pytest.raises(ValidationError):
        GetStockLevelInput.model_validate({"product_id": "invalid-uuid"})


def test_low_stock_items_input_rejects_extra_args():
    inp = GetLowStockItemsInput.model_validate({})
    assert isinstance(inp, GetLowStockItemsInput)

    with pytest.raises(ValidationError):
        GetLowStockItemsInput.model_validate({"extra_param": "foo"})
