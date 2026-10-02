from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.ai.contracts.period import DateRange, PeriodType, RelativePeriod, ReportingPeriod
from app.ai.errors import InvalidDateRangeError
from app.ai.handlers.utils import resolve_period_boundaries, resolve_previous_period_boundaries


def test_valid_relative_reporting_period():
    period = ReportingPeriod(
        period_type=PeriodType.RELATIVE,
        relative_period=RelativePeriod.MONTH,
    )
    assert period.period_type == PeriodType.RELATIVE
    assert period.relative_period == RelativePeriod.MONTH
    assert period.date_range is None


def test_valid_date_range_reporting_period():
    dr = DateRange(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
    period = ReportingPeriod(period_type=PeriodType.DATE_RANGE, date_range=dr)
    assert period.period_type == PeriodType.DATE_RANGE
    assert period.date_range.start_date == date(2026, 9, 1)
    assert period.relative_period is None


def test_invalid_date_range_inverted_dates():
    with pytest.raises(InvalidDateRangeError):
        DateRange(start_date=date(2026, 9, 30), end_date=date(2026, 9, 1))


def test_invalid_date_range_same_day():
    with pytest.raises(InvalidDateRangeError):
        DateRange(start_date=date(2026, 9, 30), end_date=date(2026, 9, 30))


def test_invalid_relative_period_with_date_range():
    dr = DateRange(start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
    with pytest.raises(ValueError, match="date_range must be null"):
        ReportingPeriod(
            period_type=PeriodType.RELATIVE,
            relative_period=RelativePeriod.MONTH,
            date_range=dr,
        )


def test_invalid_date_range_period_missing_range():
    with pytest.raises(ValueError, match="date_range is required"):
        ReportingPeriod(period_type=PeriodType.DATE_RANGE)


def test_resolve_period_boundaries_month():
    period = ReportingPeriod(
        period_type=PeriodType.RELATIVE,
        relative_period=RelativePeriod.MONTH,
    )
    tz = ZoneInfo("Africa/Nairobi")
    ref_now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=tz)

    utc_start, utc_end = resolve_period_boundaries(period, reference_now=ref_now)

    # 2026-09-01 00:00:00 EAT is 2026-08-31 21:00:00 UTC (EAT is UTC+3)
    assert utc_start == datetime(2026, 8, 31, 21, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert utc_end == datetime(2026, 9, 30, 21, 0, 0, tzinfo=ZoneInfo("UTC"))


def test_resolve_period_boundaries_date_range():
    dr = DateRange(start_date=date(2026, 9, 1), end_date=date(2026, 9, 5))
    period = ReportingPeriod(period_type=PeriodType.DATE_RANGE, date_range=dr)

    utc_start, utc_end = resolve_period_boundaries(period)

    # Half-open boundary: end_date 2026-09-05 includes entire day up to 2026-09-06 00:00:00 EAT
    assert (utc_end - utc_start).days == 5


def test_resolve_previous_period_boundaries():
    dr = DateRange(start_date=date(2026, 9, 10), end_date=date(2026, 9, 14))
    period = ReportingPeriod(period_type=PeriodType.DATE_RANGE, date_range=dr)

    prev_start, prev_end = resolve_previous_period_boundaries(period)
    assert (prev_end - prev_start).days == 5


@pytest.mark.parametrize(
    ("relative_period", "reference_date", "expected_start", "expected_end"),
    [
        (RelativePeriod.DAY, date(2026, 9, 30), date(2026, 9, 29), date(2026, 9, 30)),
        (RelativePeriod.WEEK, date(2026, 9, 30), date(2026, 9, 21), date(2026, 9, 28)),
        (RelativePeriod.MONTH, date(2026, 9, 15), date(2026, 8, 1), date(2026, 9, 1)),
        (RelativePeriod.YEAR, date(2026, 9, 15), date(2025, 1, 1), date(2026, 1, 1)),
        (RelativePeriod.MONTH, date(2024, 3, 15), date(2024, 2, 1), date(2024, 3, 1)),
    ],
)
def test_resolve_previous_relative_period_boundaries(
    relative_period: RelativePeriod,
    reference_date: date,
    expected_start: date,
    expected_end: date,
):
    period = ReportingPeriod(period_type=PeriodType.RELATIVE, relative_period=relative_period)
    reference_now = datetime.combine(reference_date, datetime.min.time(), tzinfo=ZoneInfo("UTC"))

    prev_start, prev_end = resolve_previous_period_boundaries(period, reference_now=reference_now)

    local_tz = ZoneInfo("Africa/Nairobi")
    assert prev_start.astimezone(local_tz).date() == expected_start
    assert prev_end.astimezone(local_tz).date() == expected_end
