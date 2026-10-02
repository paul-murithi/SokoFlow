"""Shared Reporting Period Contract.

Defines calendar-level period intent from the LLM, enforcing valid combinations
of relative periods and explicit date ranges.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from app.ai.errors import InvalidDateRangeError


class PeriodType(StrEnum):
    RELATIVE = "relative"
    DATE_RANGE = "date_range"


class RelativePeriod(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class DateRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "DateRange":
        if self.start_date >= self.end_date:
            raise InvalidDateRangeError(
                f"Start date ({self.start_date}) must be before end date ({self.end_date})."
            )
        return self


class ReportingPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_type: PeriodType
    relative_period: RelativePeriod | None = None
    date_range: DateRange | None = None

    @model_validator(mode="after")
    def validate_period_structure(self) -> "ReportingPeriod":
        if self.period_type == PeriodType.RELATIVE:
            if self.relative_period is None:
                raise ValueError("relative_period is required when period_type is 'relative'.")
            if self.date_range is not None:
                raise ValueError("date_range must be null when period_type is 'relative'.")
        elif self.period_type == PeriodType.DATE_RANGE:
            if self.date_range is None:
                raise ValueError("date_range is required when period_type is 'date_range'.")
            if self.relative_period is not None:
                raise ValueError("relative_period must be null when period_type is 'date_range'.")
        return self
