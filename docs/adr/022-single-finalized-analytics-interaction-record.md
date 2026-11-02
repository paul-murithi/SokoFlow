# ADR 022: Single Finalized Analytics Interaction Record

**Date:** 2026-11-02
**Status:** Accepted

---

## Context

Analytics needs enough information to diagnose proposal failures, repairs,
usage gaps, and terminal outcomes. Persisting every provider attempt as an
independent event would increase storage and complicate the relationship
between one merchant interaction and its internal execution steps.

## Options Considered

### Option A: One event per logical interaction

Persist one finalized record containing a bounded `attempts` collection with
proposal, repair, validation/execution, latency, and usage details.

**Pros:**

- Maps directly to the merchant's logical analytics interaction.
- Preserves the initial invalid proposal and repaired proposal together.
- Reduces write volume and avoids partial multi-record histories.
- Supports success, empty-result, failure, and guardrail outcomes uniformly.

**Cons:**

- Attempt-level querying requires inspecting the nested collection.
- A record can be lost if the process crashes before finalization.
- The bounded collection requires careful size and sensitive-data controls.

### Option B: One meaningful attempt event plus a final interaction event

Persist separate records for attempts and then a terminal interaction record.

**Pros:**

- Attempt-level queries and dashboards are straightforward.
- Intermediate progress can be visible before finalization.

**Cons:**

- Creates multiple records for one logical interaction.
- Requires correlation, ordering, and cleanup when finalization fails.
- Increases persistence load and duplicate/partial-history risk.

### Option C: One final interaction record plus separate provider-attempt records

Keep the final record and add provider-attempt records only when usage or
failure visibility requires them.

**Pros:**

- Offers detailed provider-level analysis when justified.
- Avoids forcing every interaction to store all attempt detail separately.

**Cons:**

- Still introduces multiple persistence paths and correlation requirements.
- Makes “only when needed” policy subjective and operationally complex.
- Is unnecessary while a bounded attempts collection provides the required
  diagnostics.

## Decision

Chose **Option A**. The system persists one finalized interaction record per logical
analytics-processing interaction, with a bounded `attempts` collection.
Logging is best effort and must never alter the merchant-facing result or
trigger another analytics invocation.

## Consequences

- Initial and repaired proposals remain observable in one record.
- Guardrail rejections can be recorded without provider fields.
- Logger persistence failures are reported independently and do not replace
  analytics successes or failures.
- Separate attempt records remain future work only if operational evidence
  shows the compact record is insufficient.
