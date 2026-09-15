# ADR 007: Best-Effort Low-Stock Alert Enqueue

**Date:** 2026-09-15
**Status:** Accepted


## Context

SokoFlow needs to notify a shop when a sale causes a product to enter its low-stock state.

The sale and inventory deduction are performed inside a database transaction. After the transaction succeeds, the application may enqueue a Celery task to send the low-stock alert.

This creates a reliability boundary:

* The database transaction can succeed.
* The subsequent Celery task enqueue can fail, for example if Redis is unavailable.
* The sale should not be rolled back solely because an alert could not be queued.

The W15 specification describes a simple flow where the worker performs the sale and inventory update, checks the low-stock condition, and enqueues the alert task. It does not require a durable event/outbox mechanism or guaranteed alert delivery.

The project is also an MVP with limited scope and does not currently require distributed event infrastructure.

---

## Options Considered

### Option A: Best-Effort Celery Enqueue After Transaction

**What it is:**
Commit the sale and inventory changes first. If the sale causes the product to enter low-stock status, enqueue the Celery alert task after the database transaction succeeds.

**Pros:**

* Matches the W15 specification.
* Keeps the implementation simple.
* Keeps database transaction logic separate from notification delivery.
* Avoids introducing an outbox/event table and additional processing infrastructure.
* A failed notification does not invalidate a successful sale.

**Cons:**

* An alert can be lost if the database transaction succeeds but task enqueueing fails.
* There is no durable record of an alert that still needs to be delivered.
* Guaranteed delivery would require additional mechanisms later.

---

### Option B: Transactional Outbox / Durable Alert Event

**What it is:**
Record a low-stock alert event in PostgreSQL as part of the same transaction as the sale and inventory update. A separate worker would later process the stored event and deliver the alert.

**Pros:**

* The low-stock event is persisted atomically with the sale.
* Alert delivery can be retried after infrastructure failures.
* Provides a stronger reliability guarantee.
* Separates business events from immediate task delivery.

**Cons:**

* Introduces additional database tables and processing logic.
* Requires an outbox/event-processing mechanism.
* Adds operational and testing complexity.
* Goes beyond the current W15 specification and MVP requirements.

---

## Decision

**Chosen option:** Option A: Best-Effort Celery Enqueue After Transaction

---

## Rationale

The MVP does not require guaranteed low-stock alert delivery, and the W15 specification explicitly describes the simpler transaction-then-enqueue flow.

The database remains the source of truth for the sale and inventory state. A notification failure should not cause a valid sale to fail or be rolled back.

The best-effort approach provides the required functionality with substantially less complexity. Introducing an outbox would solve a real reliability problem, but that problem is outside the current product requirements and would add infrastructure before SokoFlow needs it.

This is an intentional 80/20 tradeoff: accept a small possibility of losing an alert in exchange for keeping the MVP architecture straightforward.

---

## Consequences

### Positive

* Sale and inventory operations remain transactional and authoritative.
* Low-stock notification logic stays outside the database transaction.
* The implementation remains small and aligned with the W15 specification.
* No additional event/outbox infrastructure is required.

### Negative / Tradeoffs

* A low-stock alert may be lost if task enqueueing fails after the transaction commits.
* The system does not provide guaranteed notification delivery.
* Recovering missed alerts would require manual investigation or a future reliability mechanism.

### Future Work

* Revisit durable alert delivery if SokoFlow requires stronger notification guarantees.
* Consider a transactional outbox or durable alert/event table if notification loss becomes unacceptable.
* Re-evaluate this decision if the system grows to require reliable asynchronous event processing across multiple consumers.

---

## Notes

The distinction between **business state** and **notification delivery** is intentional:

* The sale and resulting inventory state are authoritative.
* `entered_low_stock` is a fact produced by the completed sale transaction.
* Sending the notification is a secondary side effect.

A failure to send the notification does not mean the sale itself failed.
