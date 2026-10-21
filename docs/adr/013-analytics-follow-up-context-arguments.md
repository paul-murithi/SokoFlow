# ADR 013: Analytics Follow-up Context Argument Representation

**Date:** 2026-10-21
**Status:** Accepted

---

## Context

Analytics follow-up context is stored in the Redis-backed session as the
arguments for the last successful tool call. Reporting-period arguments can
also be resolved into concrete timezone-aware execution boundaries, but doing
so introduces a broader context model and changes the semantics of relative
periods such as "today".

## Decision

For the MVP, successful analytics follow-up context stores the backend-validated
tool arguments. The existing period representation remains the conversational
representation, and the validated arguments are carried through the existing
`ToolExecutionResult` envelope before being stored in `PriorCallContext`.

Period resolution remains an execution-time concern. It is not persisted in
follow-up context for this MVP.

## Consequences

* Follow-ups receive arguments that passed backend validation rather than the
  unvalidated model proposal.
* The change reuses the existing execution envelope and session context.
* Relative periods may resolve to a different concrete interval if a request
  is executed again after the calendar period changes.

## Future Revisit

If deterministic replay, auditability, or exact "same period" follow-ups become
requirements, extend the context with an immutable execution snapshot containing
the effective timezone, reference time, and resolved half-open boundaries. Keep
that snapshot alongside the validated semantic arguments rather than replacing
them.
