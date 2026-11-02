# ADR 021: Bounded Analytics Provider Repair Exposure

**Date:** 2026-11-02
**Status:** Accepted

---

## Context

Model proposals can contain repairable tool or schema mistakes. Repairs
improve successful routing, but unbounded retries would increase latency and
provider cost. Provider, domain, and infrastructure failures are not model
proposal errors and must not trigger automatic repair.

## Options Considered

### Option A: Rely on the existing bounded repair policy

Permit at most one repair for an eligible proposal, resulting in no more than
two provider invocations per logical interaction.

**Pros:**

- Reuses an existing, tested contract.
- Makes the maximum provider exposure explicit and easy to reason about.
- Avoids a second Redis or database invocation counter.
- Preserves repair value for unknown tools, multiple calls, and schema errors.

**Cons:**

- A repaired interaction can still cost twice as much as a normal interaction.
- The policy must remain enforced in the orchestrator and covered by tests.
- A single repair may be insufficient for unusually difficult proposals.

### Option B: Add a separate provider-invocation limit

Track and enforce provider-call reservations or a second per-interaction
counter in addition to the repair policy.

**Pros:**

- Provides a second independently visible enforcement mechanism.
- Could support future provider-specific limits.

**Cons:**

- Duplicates the existing maximum-two-call invariant.
- Adds state and failure paths without reducing the already bounded exposure.
- Risks inconsistent accounting between logical interactions and repair calls.

## Decision

Chose **Option A**. The existing bounded repair policy is authoritative:
one initial provider invocation plus at most one eligible repair. Do not add a
separate provider-invocation quota or reservation counter in v1.

## Consequences

- Normal interactions generally use one provider invocation.
- Repair-eligible interactions use at most two.
- Provider transport, domain, and infrastructure failures do not receive
  unauthorized model retries.
