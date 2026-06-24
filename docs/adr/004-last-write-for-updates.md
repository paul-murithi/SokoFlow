# ADR 004: Last Write Wins Strategy for Product Updates

## Date

2026-06-24

## Status

Accepted

---

## Context

The system is built for SMEs (small and medium enterprises), primarily used by small shop owners (e.g., mama mboga businesses and retail kiosks). These users typically:

- Operate single- or low-user environments per shop
- Do not frequently perform simultaneous edits on the same resource
- Prioritize simplicity, speed, and reliability over advanced concurrency guarantees
- Expect predictable behavior without complex conflict resolution flows

The application currently uses a straightforward PATCH-based update model where incoming changes are applied directly to database entities.

A key design question is how to handle concurrent updates to the same product record.

---

## Options Considered

### Option 1: Last Write Wins (Current Approach)

**Description:**
Whichever transaction commits last overwrites previous updates.

**Pros:**

- Simple to implement and maintain
- No additional database overhead
- Fast performance with minimal locking complexity
- Fits low-concurrency SME usage patterns
- Keeps service layer clean and straightforward

**Cons:**

- Silent overwrites can occur
- No built-in conflict detection
- Risk of one user unintentionally overwriting another user’s changes

---

### Option 2: Optimistic Locking (Versioning)

**Description:**
Add a version field to detect concurrent modifications. Updates fail if the version has changed since read.

**Pros:**

- Prevents lost updates
- Explicit conflict detection
- More correct in multi-user environments
- Industry standard for collaborative systems

**Cons:**

- Increased complexity in API and frontend
- Requires retry or conflict resolution flows
- Slightly more database overhead
- Overkill for most SME workflows

---

### Option 3: Pessimistic Locking

**Description:**
Lock rows during updates to prevent concurrent modification.

**Pros:**

- Strong consistency guarantees
- Prevents concurrent write conflicts entirely

**Cons:**

- Poor scalability
- Increased latency
- Risk of blocking or deadlocks
- Bad UX for slow or unreliable network environments
- Not suitable for high-latency mobile users

---

## Rationale

The system prioritizes **simplicity, usability, and operational efficiency** over strict concurrency correctness.

Given the target users:

- Most shops operate with a single active staff member per product edit session
- Concurrent updates on the same product are rare
- The business impact of occasional overwrites is low compared to the complexity introduced by conflict resolution systems

Therefore, **Last Write Wins is accepted as the default behavior**.

The system intentionally avoids premature optimization for concurrency scenarios that are statistically unlikely in the target deployment context.

---

## Consequences

### Positive

- Simple and predictable backend behavior
- Fast development and iteration speed
- Minimal cognitive load for developers
- Lower infrastructure and database complexity
- Better performance under typical SME workloads

### Negative

- Possible silent overwrites in rare concurrent edits
- No audit trail of conflicting updates by default
- Not suitable for collaborative editing scenarios
- May require future refactoring if product scales into multi-user enterprise use cases

---

## Future Evolution

If the product evolves toward higher concurrency usage (e.g., multi-branch businesses, warehouse coordination systems, or enterprise clients), the following upgrades may be introduced:

- Optimistic locking via `version` or `updated_at` fields
- Conflict detection and resolution UI
- Audit logs for change tracking
- Event sourcing for critical entities (e.g., inventory, pricing)

At that stage, concurrency control will shift from implicit behavior (last write wins) to explicit conflict management.
