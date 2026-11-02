# ADR 018: Count Every Analytics-Processing Message

**Date:** 2026-11-02
**Status:** Accepted

---

## Context

Analytics requests can span multiple incoming messages. A merchant may ask a
new question, send a follow-up, or select a product after disambiguation.
Some messages can also trigger a bounded model repair. The quota must measure
the workload entering analytics without charging internal execution attempts
as if they were new merchant requests.

## Options Considered

### Option A: Count every analytics-processing message

Count one unit when an incoming message enters the analytics-processing
router. Follow-ups and disambiguation replies count; repairs and tool calls do
not.

**Pros:**

- Measures every externally initiated analytics workload.
- Prevents multi-turn conversations from bypassing the quota.
- Keeps accounting independent of provider retry behavior.
- Gives a simple atomic Redis operation one clear unit to admit or reject.

**Cons:**

- A follow-up may feel like part of an existing question but consumes another
  unit.
- A merchant can reach the limit faster during a long conversation.

### Option B: Count only new analytics operations

Count only the first message that starts an analytics question and exclude
follow-ups or disambiguation replies.

**Pros:**

- Better reflects a user-visible question rather than each message.
- Allows a multi-turn operation to complete without additional quota cost.

**Cons:**

- Requires stateful classification of new operations versus continuation
  messages.
- Makes quota usage dependent on conversation state and routing details.
- Allows unlimited or disproportionately large follow-up workloads.

## Decision

Chose **Option A**. Every incoming message entering analytics processing
consumes one unit. Internal repairs and tool executions do not consume units.

## Consequences

- Quota behavior is predictable and resistant to retry/accounting ambiguity.
- Product-selection replies are protected by the same analytics guardrail.
- The fixed unit intentionally favors resource protection over operation-level
  semantics.
