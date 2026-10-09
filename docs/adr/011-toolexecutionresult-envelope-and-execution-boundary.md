# ADR 011: ToolExecutionResult Envelope and Execution Boundary

**Date:** 2026-10-08
**Status:** Accepted

---

## Context

In SokoFlow Phase 3, LLM function-calling proposals must be executed deterministically against internal backend service handlers.

Without a standardized execution boundary and result envelope:
* Application components (such as Orchestrator) would need to parse raw domain service output models directly for every tool.
* Tool execution failures (unknown tool, structural schema error, domain error, infrastructure failure) would be handled inconsistently across different tool execution paths.
* Execution metadata (status, tool identity, error categorization) would mix directly with domain business payload fields.

---

## Decision

We introduce `ToolExecutor` and the `ToolExecutionResult` envelope as the formal execution boundary between LLM tool call proposals and SokoFlow service logic.

### 1. Architectural Boundary Separation

* **`ToolRegistry`**: Single source of truth defining available tool definitions, schemas, and handler bindings.
* **`ToolExecutor`**: Execution boundary that resolves tools via `ToolRegistry`, enforces structural schema validation (`ToolValidator`), invokes backend handlers with trusted `shop_id` context, and catches execution exceptions.
* **`ToolExecutionResult`**: Standardized envelope wrapping execution outcomes.

### 2. `ToolExecutionResult` Envelope Model

```python
ToolExecutionResult
├── status: "success" | "failure"
├── tool: str (tool name)
├── data: Any | None (structured domain output model on success)
└── error: ToolExecutionError | None (structured error details on failure)
```

The `ToolExecutor` owns execution metadata (envelope status, error classification), while preserving tool-specific domain output models (`GetSalesSummaryOutput`, `GetStockLevelOutput`, etc.) as the `data` payload.

### 3. Execution Invariants

* **No LLM Authority:** LLM tool calls are treated as proposals. The backend validates and decides execution.
* **Strict Resolution:** Rejects unknown tools cleanly (`ToolNotFoundError`) without fuzzy matching or guessing.
* **Pre-Execution Validation:** Performs structural schema validation before calling service handlers.
* **No Retries in Executor:** `ToolExecutor` reports execution results. Retry and conversational recovery policies are owned by the Orchestrator.

---

## Consequences

### Positive

* **Decoupled Execution Envelope:** The Orchestrator interacts with a uniform `ToolExecutionResult` envelope regardless of which specific tool was executed.
* **Independent Domain Payloads:** Avoids a single monolithic schema containing every tool's business fields.
* **Deterministic Failures:** Rejects invalid parameters or unknown tools before touching PostgreSQL or Redis.
* **Clear Retry Separation:** Keeps recovery policy in Orchestration rather than mixing retry logic inside the executor.

### Negative / Tradeoffs

* Extra envelope wrapper around domain output payloads.
* Downstream callers must access domain data via `result.data`.

---

## References

* SokoFlow Phase 3 Dev Guide (`docs/sokoflow-phase3-spec.pdf`, Week 2 Timeline)
* ToolExecutor (`app/ai/executor.py`)
* Execution Envelope Contracts (`app/ai/contracts/execution.py`)
* ADR 010: LLM Provider Boundary and Normalized Contract (`docs/adr/010-llm-provider-boundary-and-normalized-contract.md`)
