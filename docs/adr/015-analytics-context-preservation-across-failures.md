# ADR 015: Preservation of Last Successful Analytics Context Across Execution Failures

**Date:** 2026-10-27
**Status:** Accepted

---

## Context

SokoFlow analytics supports conversational multi-turn follow-ups (e.g. asking "What were my sales today?" followed by "and yesterday?"). Follow-up context is persisted in the Redis-backed `UserSession.context.last_analytics_call` as a `PriorCallContext` containing the tool name, validated arguments, and timestamp.

During conversation, subsequent user queries or model proposals may fail:
- A user asks an uninterpretable question resulting in zero tool calls.
- The model proposes an invalid tool or invalid arguments that fail repair.
- The backend rejects an argument (e.g. product not found).
- A transient network or database outage occurs.
- The context freshness window expires.

A clear policy is required to govern how session context is updated or preserved when an interaction does not result in successful execution.

## Decision

1. **`last_analytics_call` Represents Successful Execution Only:**
   - `last_analytics_call` is updated **only** when a tool executes successfully to completion (`ANSWERED` or `ANSWERED_EMPTY`).
   - Failed tool proposals, exhausted repairs, domain rejections, infrastructure errors, and zero-tool-call queries **MUST NOT** overwrite, corrupt, or clear the existing `last_analytics_call`.

2. **Explicit Disambiguation Context Isolation:**
   - When a tool requires product disambiguation (`NEEDS_SELECTION`), the pending call is stored separately in `pending_analytics_call` while the session transitions to `ANALYTICS_PRODUCT_SELECTION`.
   - `last_analytics_call` is updated only after the user resolves the choice and the pending tool executes successfully.
   - If execution of the pending tool fails, `last_analytics_call` remains unchanged, and pending state is cleaned up.

3. **Time-Bound Context Expiration Without Silent Replay:**
   - Follow-up context freshness is checked via `AnalyticsRoutingPolicy.has_fresh_context()` against `analytics_follow_up_ttl_seconds` (default 600s).
   - Once expired, prior context is omitted from model generation messages.
   - The system never silently reconstructs or infers expired context. If the model cannot interpret an expired follow-up as a standalone query, the neutral zero-tool-call fallback applies.

## Consequences

- **Fault Tolerance for Follow-ups:** A merchant who makes a typo or asks an uninterpretable intermediate question does not lose their previous valid query context and can rephrase their follow-up.
- **Clean Session Invariants:** Session context is never left in a partially mutated or corrupt state following a failure.
- **Privacy & Relevance:** Stale context is dropped deterministically after TTL expiration without leaking past operations into unrelated future requests.
