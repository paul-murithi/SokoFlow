# ADR 023: Separate Provider Benchmarking from Application Integration

**Date:** Not recorded
**Decision status:** Accepted

## Context

The original Week 1 analytics benchmark was introduced to compare LLM providers based on their ability to interpret merchant queries and generate appropriate analytics tool calls.

Its primary evaluation objectives were:

- Correct tool selection.
- Correct argument generation.
- Provider response validity.
- Provider latency.
- Estimated provider cost.

At the time, the analytics architecture had not yet established the explicit boundaries between `LLMClient`, `Orchestrator`, `ToolExecutor`, handlers, and business services. The benchmark therefore used the existing conversation entry point to exercise provider requests:

```python
await asyncio.wait_for(
    conversation_tasks.conversation(_payload(query, index)),
    timeout
)
```

Subsequent architectural development established clearer boundaries between model interpretation, tool validation, and backend business logic.

A recent investigation of the benchmark implementation identified that its execution path extends beyond provider interaction.

Some benchmark cases execute the real conversation flow, including:

- Model interpretation and argument generation.
- Tool validation.
- Handler execution.
- Product resolution.
- PostgreSQL queries.

In particular, stock-level and product-price cases resolve products by name through the product resolver. This invokes fuzzy-search SQL using PostgreSQL's `similarity()` function, which requires the `pg_trgm` extension.

The benchmark fixture setup currently uses `Base.metadata.create_all()`, which does not independently establish extensions enabled through Alembic migrations.

Consequently, running the existing integrated benchmark against a separate `BENCHMARK_DB` requires the appropriate database migrations and extension setup.

However, the original provider-comparison objective does not inherently require handler execution, product resolution, or database access.

There is therefore a distinction between the benchmark's original evaluation objective and its current execution boundary.

This was discovered during Week 6 demo preparation, while considering the separation of `MAIN_DB`, `TEST_DB`, and `BENCHMARK_DB`.

The Week 6 demo is the immediate priority. Changes to the existing benchmark implementation are deferred until after the demo.

---

## Options Considered

### Option A: Preserve the Integrated Benchmark

**What it is:**

Retain the current conversation-based benchmark implementation, including handler execution, product resolution, and database queries.

Continue using a dedicated `BENCHMARK_DB`, applying the application's Alembic migrations and required PostgreSQL extensions.

**Pros:**

- Preserves the existing benchmark implementation and execution behaviour.
- Exercises the real application integration path.
- Exposes failures that occur beyond LLM interpretation.
- Requires minimal immediate changes.

**Cons:**

- Couples provider comparison to application business logic and database infrastructure.
- Database or handler failures can affect benchmark completion independently of provider quality.
- Whole-conversation timeouts can include non-provider execution time.
- Successful handler execution does not independently establish that the model generated the exact expected arguments.
- Database dependencies increase benchmark setup and maintenance requirements.

---

### Option B: Separate Provider Benchmarking from Application Integration

**What it is:**

Refactor the original Week 1 benchmark to evaluate providers independently through the `LLMClient` boundary.

Supply identical merchant queries and tool definitions to each provider. Capture the provider responses and compare tool selection and generated arguments against an independently maintained answer key.

Measure provider latency and cost at the appropriate LLMClient boundary.

Keep application integration and database execution in separate tests or benchmarks.

**Pros:**

- Aligns the benchmark execution boundary with its original provider-comparison objective.
- Removes unnecessary dependencies on handlers, business services, PostgreSQL, and `pg_trgm`.
- Isolates provider failures from application execution failures.
- Makes latency and cost measurements easier to interpret.
- Allows provider comparisons without requiring application database fixtures.
- Establishes a cleaner separation between model evaluation and application correctness.

**Cons:**

- Requires refactoring the existing benchmark.
- Changes the benchmark's execution semantics, making historical results potentially incomparable.
- Requires an independently maintained answer key and explicit argument-level evaluation.
- No longer measures the complete application execution path.
- Does not replace integration testing.

---

## Decision

**Chosen option:** Option B: Separate Provider Benchmarking from Application Integration (Deferred).

---

## Rationale

The original Week 1 benchmark was intended to compare LLM providers, not validate the complete application execution path.

Using the conversation entry point was a practical implementation choice at a time when explicit architectural boundaries had not yet been established.

However, the current architecture provides a cleaner evaluation boundary through `LLMClient`.

Separating provider evaluation from application integration would improve measurement isolation.

A provider should not receive a failed benchmark result because a downstream product resolver, database query, or handler failed after the provider generated a correct response.

Likewise, provider latency should not be confused with total conversation execution time.

Option A remains technically valid if the objective is to benchmark integrated application behaviour. However, that is a different evaluation objective and should be treated as such.

Option B better matches the original provider-comparison objective while allowing application integration to be evaluated independently.

The refactoring is deliberately deferred to avoid introducing unnecessary changes during Week 6 demo preparation.

---

## Consequences

### Positive

- Preserves the distinction between provider quality and application execution correctness.
- Establishes clearer benchmark responsibilities.
- Reduces unnecessary infrastructure dependencies for isolated provider evaluation.
- Creates an opportunity to improve benchmark reproducibility and measurement accuracy.
- Allows the existing application integration path to be tested independently.

### Negative / Tradeoffs

- The integrated benchmark still requires a dedicated database, migrations, and `pg_trgm`.
- Historical provider-comparison results cannot automatically be compared with results from a refactored implementation.

## Current Implementation

Provider evaluation and integrated application benchmarking now have separate
entry points:

- `tools/eval_harness.py` evaluates the analytics interpretation and
  tool-execution boundary through `LLMClient`, the orchestrator, and a
  validation-only executor. It uses a mocked database session and does not
  measure real repository execution.
- `tools/analytics_benchmark.py` exercises the integrated conversation path,
  including database queries, and requires its dedicated benchmark database.

Treat results from these tools as different measurements: provider/tool proposal
quality is not end-to-end application correctness, and integrated latency is
not provider-only latency.
