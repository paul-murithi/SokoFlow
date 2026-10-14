# ADR 012: Analytics Routing Inside IDLE Intent Dispatch

## Context

Week 3 of Phase 3 adds natural-language analytics to the existing WhatsApp/FSM pipeline. Analytics questions are open-ended, so the regex-based Intent Resolver cannot recognize them. Today, any message the resolver does not match is classified as `UNKNOWN`, and `_handle_idle()` responds by raising `InvalidInputError`, which produces `MessageKey.UNKNOWN_INTENT` and affects the error counter.

A decision is needed on where unmatched messages get routed to analytics, because that choice determines who owns session updates, error semantics and `FSMResult` construction.

- **Trigger:** the Week 3 spec requires an `ANALYTICS_QUERY` path through the existing webhook and FSM, including follow-ups ("and yesterday?").
- **Why now:** routing placement affects the Orchestrator-to-handler contract, the error counter policy and the session save flow, all of which are being built this week.
- **Constraints:**
  - The worker pipeline is uniform: retrieve session, `fsm_engine.process_message()`, atomic CAS save, `render_message`, send.
  - The resolver should remain a pure regex classifier.
  - An LLM round trip (about 1.3s average, with a possible bounded retry) now sits between session read and session save.
  - Every LLM call has a cost, so not every unmatched message should reach the model.

---

## Options Considered

### Option A: Route inside `_handle_idle()`

**What it is:**
When the resolver returns `UNKNOWN`, `_handle_idle()` asks a routing policy whether to escalate. If yes, it calls the analytics flow directly and returns that flow's `FSMResult`. If no, it falls through to the existing unknown-intent behavior.

**Pros:**
- Routing stays inside the existing intent-dispatch step, which is already where intents become actions.
- The analytics result, any session context update and the error counter decision are all produced inside one FSM call, so the worker keeps its single CAS save.
- `FSMResult` construction stays in one place, owned by the FSM layer.
- The session remains IDLE on the happy path with no extra state.

**Cons:**
- Requires a deliberate policy for preserving existing unknown-intent behavior and the error counter.
- `_handle_idle()` gains a dependency on the routing policy and the analytics flow.
- The FSM step now includes an LLM round trip, which affects time limits and the CAS window.

---

### Option B: Route after `process_message()` returns

**What it is:**
The FSM processes the message as it does today. If the worker sees `MessageKey.UNKNOWN_INTENT`, it decides whether to invoke analytics and, if so, runs it outside the FSM.

**Pros:**
- Keeps AI routing policy out of the resolver and the FSM handler.
- Leaves the existing FSM code path unchanged.

**Cons:**
- By the time the worker sees `UNKNOWN_INTENT`, the FSM has already treated the message as an error: the counter may have incremented, context may have mutated, and an error `FSMResult` exists.
- The worker would have to override or undo that result, or perform a second session update, producing either two CAS saves or a worker editing another component's output.
- The worker would need domain knowledge about when "unknown" actually means "analytics", breaking its role as a uniform pipeline.
- Analytics execution would sit outside the FSM's normal processing boundary, making session and error semantics harder to reason about and test.

---

## Decision

**Chosen option:** Option A: Route inside `_handle_idle()`, with escalation policy extracted into a separate routing policy component.

---

## Rationale

- **Routing is intent dispatch.** Deciding what a message means already belongs to the IDLE handler's intent dispatch. Analytics is another outcome of that step that happens to answer immediately instead of starting a flow.
- **Single boundary for state and errors.** Option A keeps the result, session updates and error counter decision inside one FSM call. Option B splits them across the FSM and the worker, which is the structural problem, not just a delicate one.
- **Policy stays out of the resolver and handler body.** The resolver continues to return `UNKNOWN` as a fact about regex matching. A small routing policy component answers one question: should this `UNKNOWN` escalate to analytics for this message and shop? Feature flags, per-shop limits and pre-filters live behind that interface. `_handle_idle()` contains a single conditional.
- **Cost control.** Escalation is a policy decision, so stray messages (greetings, typos) need not trigger a paid model call.
- **Error counter policy.** The counter measures user confusion, so it moves only when the user was not understood:

| Situation | Error counter |
|---|---|
| Policy declines escalation | Unchanged: increments as today |
| Analytics answers (data, empty data, needs selection) | No increment: the message was understood |
| Model returns no tool call | Increments: message not understood, reply maps back to the existing unknown message |
| LLM unavailable, timeout or other infrastructure failure | No increment: not the user's fault |

---

## Consequences

### Positive
- The worker pipeline stays unchanged and uniform.
- One CAS save covers the analytics result and any context update.
- Routing policy can change (flags, limits, pre-filters) without touching the resolver or the FSM handler body.
- Analytics routing can be tested through `_handle_idle()` with a fake policy and a fake analytics flow.

### Negative / Tradeoffs
- `_handle_idle()` now depends on two more collaborators.
- The FSM step is no longer near-instant, so the CAS conflict window widens for users who send messages in quick succession.
- Error counter behavior is now more nuanced and must be tested per outcome category.

### Future Work (optional)
- Decide and document behavior on CAS conflict during the slower analytics path.
- Verify the conversation task's time limit and retry settings cover the worst-case LLM round trip plus one bounded retry.
- Revisit an escape hatch for analytics questions sent while a user is mid-flow in a parked state.

---

## Notes (optional)

- The routing policy's initial rules (flag only, or flag plus per-shop limits) are not yet decided.
- What the error counter threshold actually triggers should be checked in the existing code, because it determines how much the "no tool call" and infrastructure-failure rows matter.
- Related decisions: analytics handler as adapter over an independent Orchestrator, stateless happy path with follow-up context stored as the last structured call, deterministic formatter producing `message_key` and `params`.
