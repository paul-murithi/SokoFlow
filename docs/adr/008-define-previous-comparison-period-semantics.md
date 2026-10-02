# ADR 008: Define Previous Comparison Period Semantics

**Date:** 2026-09-30
**Status:** Accepted

## Context

SokoFlow's `get_sales_trend` tool compares sales performance between a target reporting period and a comparison period.

When the caller explicitly provides a comparison period, the handler resolves that period directly:

```python
if input_data.comparison_period:
    prev_start, prev_end = resolve_period_boundaries(
        input_data.comparison_period
    )
```

When no comparison period is provided, the handler currently derives one automatically:

```python
else:
    prev_start, prev_end = resolve_previous_period_boundaries(
        input_data.period
    )
```

The existing implementation of `resolve_previous_period_boundaries()` derives the previous period by subtracting the elapsed duration of the current period:

```python
duration = curr_end - curr_start

prev_end = curr_start
prev_start = prev_end - duration
```

This is technically valid, but it introduces an ambiguity in the domain meaning of "previous period."

For example, if the current period is September:

```text
Current period:
Sep 1 ───────────────── Oct 1
          30 days
```

Duration-based comparison produces:

```text
Previous:
Aug 2 ───────────────── Sep 1
          30 days
```

A calendar-period comparison instead produces:

```text
Previous:
Aug 1 ───────────────── Sep 1
          31 days

Current:
Sep 1 ───────────────── Oct 1
          30 days
```

Both approaches are mathematically valid. They represent different business meanings.

This matters because `get_sales_trend` is a user-facing reporting tool. Without an explicit definition, different parts of the system could interpret "previous period" differently, producing comparisons that are technically consistent but semantically unexpected.

The decision is therefore needed before the reporting layer expands further.

Constraints:

- SokoFlow reporting uses calendar-relative periods such as day, week, month, and year.
- The shop's timezone determines local calendar boundaries.
- Reporting periods use half-open intervals: `[start, end)`.
- Explicitly supplied comparison periods must remain supported.
- The LLM should not independently calculate reporting boundaries.
- The reporting/domain layer should own period semantics.

---

## Options Considered

### Option A: Previous Equivalent-Duration Period

**What it is:**

Define "previous period" as the period immediately preceding the target period with the same elapsed duration.

For example:

```text
Current:   Sep 1 → Oct 1      30 days
Previous:  Aug 2 → Sep 1      30 days
```

The current `resolve_previous_period_boundaries()` implementation follows this model.

**Pros:**

- Simple and generic.
- Works naturally for arbitrary fixed-duration ranges.
- Produces comparison periods with identical elapsed durations.
- Requires minimal implementation logic.
- Useful for rolling-window comparisons such as "last 30 days vs the 30 days before that."

**Cons:**

- Does not preserve calendar semantics.
- Produces unintuitive results for variable-length calendar periods such as months and years.
- "Previous month" could no longer mean the actual previous calendar month.
- The comparison can cross calendar boundaries in ways users do not expect.
- The function name and domain meaning can become ambiguous.

---

### Option B: Previous Equivalent Calendar Period

**What it is:**

Define "previous period" as the calendar period immediately preceding the target period when the target is a calendar-relative reporting period.

Examples:

```text
DAY
Current:   Sep 30 00:00 → Oct 1 00:00
Previous:  Sep 29 00:00 → Sep 30 00:00
```

```text
WEEK
Current:   Mon Sep 28 → Mon Oct 5
Previous:  Mon Sep 21 → Mon Sep 28
```

```text
MONTH
Current:   Sep 1 → Oct 1
Previous:  Aug 1 → Sep 1
```

```text
YEAR
Current:   Jan 1 2026 → Jan 1 2027
Previous:  Jan 1 2025 → Jan 1 2026
```

Calendar boundaries are resolved using the shop's local timezone before being represented as UTC boundaries for querying.

**Pros:**

- Matches the natural meaning of previous day/week/month/year.
- Preserves calendar semantics for reporting.
- Produces intuitive comparisons for users.
- Keeps period interpretation inside the domain/reporting layer.
- Avoids assumptions that calendar periods have equal durations.
- Aligns with the existing `resolve_period_boundaries()` model.

**Cons:**

- Calendar periods do not always have equal elapsed durations.
- Requires explicit calendar-aware logic for different period types.
- Less generic than simply subtracting a `timedelta`.
- Rolling/fixed-duration comparisons require a separate concept.

---

## Decision

**Chosen option:** Option B: Previous Equivalent Calendar Period

---

## Rationale

The default comparison semantics for `get_sales_trend` will treat "previous period" as the **immediately preceding equivalent calendar period** for calendar-relative reporting periods.

This fits the product's reporting model because SokoFlow already represents reporting periods using calendar concepts such as day, week, month, and year. A user asking for a comparison of monthly sales would reasonably expect the comparison to be against the preceding calendar month, not an arbitrary interval containing the same number of elapsed days.

The distinction is particularly important for variable-length periods:

```text
September: 30 days
August:    31 days
February:  28 or 29 days
```

Equal duration is therefore not a reliable definition of an equivalent calendar period.

The existing duration-based approach remains a valid domain concept for other reporting requirements. It is useful when the requirement is explicitly based on elapsed time, such as:

> Compare the last 30 days with the preceding 30 days.

That use case should be represented explicitly rather than being implicitly treated as the meaning of "previous period."

This separation gives the reporting layer two clear concepts:

```text
Previous calendar period
        ↓
"previous month", "previous week", etc.

Previous duration window
        ↓
"the 30 days immediately before this 30-day window"
```

For SokoFlow's current `get_sales_trend` behavior, the calendar interpretation is the default.

When `comparison_period` is explicitly provided, it continues to be resolved directly using `resolve_period_boundaries()`.

---

## Consequences

### Positive

- "Previous period" has a defined domain meaning.
- Monthly, weekly, and yearly comparisons align with calendar expectations.
- The reporting layer has an explicit contract instead of relying on implementation details.
- The LLM does not need to determine or calculate comparison boundaries.
- Future developers have a documented distinction between calendar comparisons and duration-based comparisons.
- Variable-length months and years are handled according to calendar semantics rather than assumed durations.

### Negative / Tradeoffs

- `resolve_previous_period_boundaries()` can no longer be implemented as a generic duration subtraction for all period types.
- Calendar-aware logic is required for month and year boundaries.
- Calendar comparisons may contain different numbers of elapsed hours or days.
- A separate mechanism may eventually be required for rolling-window comparisons.

### Implementation

- `resolve_previous_period_boundaries()` now uses preceding local calendar boundaries
  for relative day, week, month, and year periods.
- Tests cover previous day, week, month, and year boundaries, including February in
  a leap year and timezone-aware UTC conversion.

### Future Work

- If rolling-window reporting is introduced, define a separate duration-based comparison concept rather than reusing the calendar-period resolver.

---

## Notes

The distinction is between two valid domain concepts rather than between "correct" and "incorrect" date arithmetic.

The following are both legitimate:

```text
Previous calendar period
Aug 1 → Sep 1
```

and:

```text
Previous equivalent-duration period
Aug 2 → Sep 1
```

The important decision is which meaning the product assigns to the phrase **"previous period."**

For SokoFlow's calendar-relative sales reporting, that meaning is the immediately preceding calendar period.
