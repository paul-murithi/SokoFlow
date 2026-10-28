# ADR 014: Failure Semantics and Bounded Repair Policy in Natural-Language Analytics

**Date:** 2026-10-27
**Status:** Accepted

---

## Context

In Phase 3 natural-language analytics, user queries route from WhatsApp through an FSM into an LLM orchestrator that proposes deterministic tool executions. Model interactions are inherently non-deterministic and can produce multiple classes of failure:
1. Zero tool calls proposed.
2. Unknown or unsupported tool names.
3. Multiple simultaneous tool calls.
4. Structurally invalid argument schemas.
5. Provider transport timeouts or service unavailability.
6. Malformed provider response bodies.
7. Backend business/domain rejections (e.g. product not found).
8. Database or infrastructure execution failures.

Without a well-defined boundary policy, failure recovery risks:
- Unbounded or repetitive LLM retries driving up latency and cost.
- Leaking technical exception messages, internal schemas, or tool names to merchants.
- Fabricating business results or silently executing invalid operations.
- Confusing technical system outages with legitimate zero-data query results.

## Decision

We establish an explicit failure taxonomy and bounded repair contract across the `Orchestrator`, `ToolExecutor`, and `AnalyticsFlow`:

1. **Failure Taxonomy & Distinct Outcomes:**
   - The Orchestrator reports what occurred using a discriminated, typed `AnalyticsOutcome` (`ANSWERED`, `ANSWERED_EMPTY`, `NEEDS_SELECTION`, `NO_ANALYTICS_INTENT`, `INVALID_PROPOSAL`, `ARGUMENT_VALIDATION_FAILED`, `MALFORMED_RESPONSE`, `DOMAIN_FAILURE`, `PROVIDER_UNAVAILABLE`, `INFRASTRUCTURE_FAILURE`).
   - Technical failures (infrastructure, provider) remain strictly distinct internally from business/domain rejections and from successful empty queries.

2. **Bounded 1-Attempt Repair Policy:**
   - Automatic LLM repair is permitted **at most once** and strictly for potentially repairable model proposals:
     - Unknown tool names (prompt with available active tool names).
     - Multiple tool calls (prompt to choose exactly one tool).
     - Structurally invalid arguments (prompt with Pydantic validation error summary).
   - If the second attempt fails, repair is exhausted and an explicit failure outcome is returned.
   - **No automatic LLM retries** are permitted for:
     - Zero tool calls.
     - Provider transport/timeout errors.
     - Malformed provider responses.
     - Business/domain rejections.
     - Database/infrastructure errors.

3. **Zero Tool Calls Semantics:**
   - Zero tool calls are treated as a neutral non-execution outcome (`NO_ANALYTICS_INTENT`), not an error.
   - The system executes no tool, does not retry the model, does not increment FSM error counters, and retains the user's prior successful analytics context.
   - The user receives a friendly generic recovery message (`MessageKey.ANALYTICS_INVALID_PROPOSAL`).

4. **Information Hiding in Presentation:**
   - Merchants never receive internal stack traces, database error strings, or raw validation JSON.
   - Failures map to localized message keys:
     - Generic recovery: for unhandled questions or exhausted proposal repairs.
     - Temporary failure: for provider or database outages.
     - Business explanation: for domain rejections.
     - Explicit empty explanation: for valid zero-record queries.

## Consequences

- **Bounded Latency & Predictable Costs:** LLM calls are capped at a maximum of 2 requests per merchant query, preventing runaway token usage and long latency spikes.
- **Data Integrity:** Invalid or hallucinated proposals are rejected before executing backend business logic.
- **Graceful User Experience:** Merchants receive clear, localized Swahili and English messages without technical jargon or system crashes.
- **Observability:** Internal logs and outcome structures preserve exact error types and validation details for telemetry and debugging without exposing them across user channels.
