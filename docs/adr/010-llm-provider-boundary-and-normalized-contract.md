# ADR 010: LLM Provider Boundary and Normalized Contract

**Date:** 2026-10-07
**Status:** Accepted

---

## Context

SokoFlow requires an LLM for natural-language interpretation and tool selection for WhatsApp analytics queries while remaining independent of the underlying provider (such as Groq or OpenRouter).

Directly invoking provider SDKs throughout application components introduces strong provider coupling:
* Provider request and response structures leak into application logic.
* Provider-specific exception hierarchies leak into error handling.
* Logging, latency measurement, and configuration become fragmented.
* Swapping or adding fallback providers would require invasive multi-file refactoring.

---

## Decision

We introduce `LLMClient` as the sole provider boundary and gateway within SokoFlow.

`LLMClient` will:
1. Accept a SokoFlow-owned input contract representing messages, tool definitions, and generation parameters.
2. Translate that contract into provider-specific request structures.
3. Communicate directly with the configured LLM provider API.
4. Normalize the raw provider response into a small, SokoFlow-owned output contract (`LLMResponse`).
5. Translate provider-specific exceptions into provider-agnostic application-level errors (e.g., `LLMProviderTimeoutError`, `LLMProviderAPIError`).
6. Enforce operational boundary concerns such as timeouts, retries, and latency logging.

`LLMClient` will **not**:
* Validate SokoFlow tool existence or argument schemas (owned by `ToolRegistry` and `ToolValidator`).
* Execute SokoFlow tools or access database repositories (owned by `ToolExecutor` and domain services).
* Enforce domain rules, business logic, or WhatsApp message formatting.
* Decide application-level retry policy for semantically invalid model responses (owned by Orchestration).

---

## Core Contracts

### 1. Input Contract
SokoFlow passes an application-owned input representation containing conversation messages, registered tool schemas, and parameters. `LLMClient` translates this into the provider's API payload.

### 2. Output Contract (`LLMResponse`)
`LLMClient` normalizes provider responses into a minimal SokoFlow-owned model containing only required attributes:
* `text`: Optional natural-language response string.
* `tool_calls`: Optional list of normalized tool requests, each containing `name` and `arguments`.

### 3. Error Contract
Provider-specific errors (e.g. Groq network timeouts, rate limits) are caught at the boundary and translated into application-level error types:
* **Infrastructure / Provider Faults**: `LLMProviderTimeoutError`, `LLMProviderUnavailableError`
* **Response Integrity Faults**: `LLMResponseFormatError`

---

## Consequences

### Positive

* **Provider Isolation:** Application code outside `LLMClient` has zero dependency on Groq or OpenAI SDK types.
* **Stable Internal Interface:** Provider response payloads do not leak into downstream orchestrators or executors.
* **Clear Error Taxonomy:** Failure classification follows the owning boundary (`LLMClient` owns transport/translation failures; `ToolRegistry` owns tool validation failures).
* **Testability:** Simplifies unit and integration testing by allowing test suites to mock `LLMClient` using SokoFlow-owned input/output models.

### Negative / Tradeoffs

* Translation overhead between provider-specific objects and internal SokoFlow contracts.
* Additional mapping layer required when supporting new provider features.

---

## References

* SokoFlow Phase 3 Dev Guide (`docs/sokoflow-phase3-spec.pdf`)
* ADR 009: LLM Provider Selection for Analytics Function Calling (`docs/adr/009-llm-provider-selection-for-analytics-function-calling.md`)
