# ADR 020: Post-Call Provider Usage Accounting

**Date:** 2026-11-02
**Status:** Accepted

---

## Context

Provider usage and cost metadata may be missing, incomplete, or provider
specific. SokoFlow needs resource protection without introducing reservations
that can become stranded when calls time out or providers return uncertain
results.

## Options Considered

### Option A: Estimate and record usage after the call

Use the per-shop daily query quota and explicit per-call token ceiling before
the call. Capture provider usage after the call when available, distinguishing
complete, partial, and unavailable metadata.

**Pros:**

- No reservation reconciliation or abandoned reservation state.
- Preserves the analytics result even when accounting metadata is incomplete.
- Keeps provider-specific usage handling behind the provider boundary.
- The daily quota and token ceiling provide practical v1 exposure controls.

**Cons:**

- Does not guarantee an exact monetary ceiling.
- Failed or timed-out calls may still incur provider charges.
- Missing provider metadata limits cost-analysis accuracy.

### Option B: Reserve estimated cost before calling the provider

Reserve an estimated token or monetary amount, then reconcile or release it
after the provider call.

**Pros:**

- Could enforce a stricter budget if estimates were reliable.
- Makes budget admission explicit before provider work starts.

**Cons:**

- Requires reservation, release, reconciliation, and abandoned-state handling.
- Provider failures and missing usage make reconciliation uncertain.
- Adds another accounting system without current evidence that it is needed.
- Risks rejecting useful analytics based on inaccurate estimates.

## Decision

Chose **Option A**. The system will not reserve estimated monetary or token cost in v1.
Apply the configured per-call token ceiling, rely on the per-shop daily query
quota, and record provider usage after invocation without fabricating values.

## Consequences

- `actual_cost` is recorded only when the provider genuinely reports it.
- Unknown or partial usage remains explicit.
- A strict daily monetary budget can be added later if measured usage warrants
  the complexity.
