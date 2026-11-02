# ADR 019: Fixed Daily Window and Configurable Per-Shop Analytics Quota

**Date:** 2026-11-02
**Status:** Accepted

---

## Context

Analytics admission must be atomic, shop-isolated, and inexpensive to operate.
The system already uses Redis, and the quota must reset by the
`Africa/Nairobi` calendar date without a scheduled reset process.

## Options Considered

### Option A: Fixed date-stamped Redis window with per-shop quota

Use one counter per trusted shop and Nairobi date. Set a 48-hour expiry,
admit/increment atomically, and configure the quota per shop with a default of
100 messages.

**Pros:**

- Simple atomic implementation with low operational overhead.
- Shops cannot consume one another's quota.
- Date-stamped keys make daily reset behavior explicit.
- Expiry prevents abandoned counters from accumulating indefinitely.
- Per-shop configuration supports future usage tiers.

**Cons:**

- Fixed windows permit bursts around midnight.
- Per-shop configuration adds a source of configuration management.
- Redis availability becomes a prerequisite for analytics admission.

### Option B: One hard quota shared by every shop

Maintain one global analytics counter and reject requests after the shared
limit is exhausted.

**Pros:**

- Simplest counter and configuration model.
- Provides a coarse global provider-protection ceiling.

**Cons:**

- One busy shop can starve all other shops.
- Does not satisfy tenant-isolated resource ownership.
- Makes fair usage and future tiering difficult.

### Option C: Sliding window, token bucket, or scheduled reset

Use of a more precise distributed limiter or reset counters with a scheduled job.

**Pros:**

- Sliding/token-bucket approaches smooth bursts.
- A scheduled reset can make cleanup timing explicit.

**Cons:**

- Adds distributed-state and operational complexity.
- Requires more failure modes and coordination than v1 needs.
- A reset job introduces another dependency and recovery concern.

## Decision

Chose **Option A**. An atomic fixed daily Redis window per trusted shop,
derived from the Nairobi calendar date, with 48-hour expiry. The quota is
configurable per shop and defaults to 100. Do not use a global shared quota,
sliding windows, token buckets, or scheduled resets in v1.

## Consequences

- Analytics fails closed when Redis cannot provide an admission decision.
- Midnight bursts are an accepted simplicity trade-off.
- Usage tiers can be introduced without changing the limiter model.
