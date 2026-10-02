"""Date Handling and Boundary Calculation Utilities.

Converts calendar-level LLM intent (ReportingPeriod) into deterministic, timezone-aware
UTC datetime boundaries using half-open intervals [start_datetime, end_datetime).
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.ai.contracts.period import PeriodType, RelativePeriod, ReportingPeriod
from app.ai.errors import InvalidDateRangeError


def _resolve_relative_local_boundaries(
    relative_period: RelativePeriod,
    anchor_date: date,
    tz: ZoneInfo,
) -> tuple[datetime, datetime]:
    if relative_period == RelativePeriod.DAY:
        local_start = datetime.combine(anchor_date, time.min, tzinfo=tz)
        local_end = local_start + timedelta(days=1)
    elif relative_period == RelativePeriod.WEEK:
        week_start = anchor_date - timedelta(days=anchor_date.weekday())
        local_start = datetime.combine(week_start, time.min, tzinfo=tz)
        local_end = local_start + timedelta(days=7)
    elif relative_period == RelativePeriod.MONTH:
        local_start = datetime.combine(
            date(anchor_date.year, anchor_date.month, 1), time.min, tzinfo=tz
        )
        if anchor_date.month == 12:
            next_month_start = date(anchor_date.year + 1, 1, 1)
        else:
            next_month_start = date(anchor_date.year, anchor_date.month + 1, 1)
        local_end = datetime.combine(next_month_start, time.min, tzinfo=tz)
    elif relative_period == RelativePeriod.YEAR:
        local_start = datetime.combine(date(anchor_date.year, 1, 1), time.min, tzinfo=tz)
        local_end = datetime.combine(date(anchor_date.year + 1, 1, 1), time.min, tzinfo=tz)
    else:
        # TODO: Unreachable due to Pydantic enum validation.
        raise ValueError(f"Unknown relative period: {relative_period}")

    return local_start, local_end


def resolve_period_boundaries(
    period: ReportingPeriod,
    local_tz_name: str = "Africa/Nairobi",
    reference_now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """
    Calculates UTC start and end datetimes for a given ReportingPeriod using half-open
    intervals [start_datetime, end_datetime).
    """
    tz = ZoneInfo(local_tz_name)
    now = reference_now.astimezone(tz) if reference_now else datetime.now(tz)
    today = now.date()

    if period.period_type == PeriodType.RELATIVE:
        rel = period.relative_period
        if rel is None:
            raise ValueError("Missing relative period specification.")
        local_start, local_end = _resolve_relative_local_boundaries(rel, today, tz)

    elif period.period_type == PeriodType.DATE_RANGE:
        dr = period.date_range
        if dr is None:
            raise InvalidDateRangeError("Missing date_range specification.")
        local_start = datetime.combine(dr.start_date, time.min, tzinfo=tz)
        local_end = datetime.combine(dr.end_date + timedelta(days=1), time.min, tzinfo=tz)

    else:
        raise ValueError(f"Unknown period type: {period.period_type}")

    utc_start = local_start.astimezone(ZoneInfo("UTC"))
    utc_end = local_end.astimezone(ZoneInfo("UTC"))

    return utc_start, utc_end


def resolve_previous_period_boundaries(
    period: ReportingPeriod,
    local_tz_name: str = "Africa/Nairobi",
    reference_now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Calculate UTC boundaries for the preceding calendar or duration period.

    Relative periods use the immediately preceding local calendar period. Explicit
    date ranges retain equivalent-duration semantics for rolling window comparisons.
    """
    if period.period_type == PeriodType.RELATIVE:
        tz = ZoneInfo(local_tz_name)
        now = reference_now.astimezone(tz) if reference_now else datetime.now(tz)
        relative_period = period.relative_period
        if relative_period is None:
            raise ValueError("Missing relative period specification.")
        current_start, _ = _resolve_relative_local_boundaries(relative_period, now.date(), tz)
        previous_start, previous_end = _resolve_relative_local_boundaries(
            relative_period,
            current_start.date() - timedelta(days=1),
            tz,
        )
        utc = ZoneInfo("UTC")
        return previous_start.astimezone(utc), previous_end.astimezone(utc)

    curr_start, curr_end = resolve_period_boundaries(period, local_tz_name, reference_now)
    duration = curr_end - curr_start
    prev_end = curr_start
    prev_start = prev_end - duration
    return prev_start, prev_end
