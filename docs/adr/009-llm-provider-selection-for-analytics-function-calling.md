# ADR 009: LLM Provider Selection for Analytics Function Calling

**Date:** 2026-10-05
**Status:** Accepted

---

## Context

In SokoFlow Phase 3, merchant natural-language questions received via WhatsApp (such as "how much did I sell today" or "what's my stock on sugar") are flagged by the intent resolver as `ANALYTICS_QUERY` intents.

To answer these questions, an LLM function-calling client converts free-text queries into structured tool calls matching frozen Pydantic schemas in `ToolRegistry` (e.g. `get_sales_summary`, `get_top_products`, `get_stock_level`). The tool executor validates these arguments and calls internal service functions without granting the LLM direct database or mutation access.

Week 1 of the Phase 3 specification mandates benchmarking 2–3 LLM provider options on function-calling reliability, latency, and cost per call against 8–10 real sample queries before committing.

### KPI Requirement

* All tool schemas frozen in writing.
* Provider chosen with documented rationale.
* At least 8 out of 10 benchmark queries correctly routed by the chosen provider (matching expected tool + valid Pydantic input schema).

---

## Options Considered

### Option 1: Groq (`openai/gpt-oss-20b`)

A managed high-throughput inference platform serving open models with native function-calling support.

* **Latency:** ~1309 ms average.
* **Cost:** ~$0.00005 per query call ($0.05 / 1M input tokens, $0.08 / 1M output tokens).
* **Function Calling Reliability:** 10/10 (100%) queries correctly routed with valid Pydantic schemas.

### Option 2: OpenRouter Free (`openrouter/free`)

An aggregator service routing requests to free tier models across providers.

* **Latency:** ~4590 ms average.
* **Cost:** $0.00.
* **Function Calling Reliability:** 2/10 (20%) queries correctly routed. Frequently failed to format nested JSON arguments (e.g., passing stringified JSON for `ReportingPeriod`) or omitted tool calls.

### Option 3: OpenRouter Llama 3.3 70B (`meta-llama/llama-3.3-70b-instruct`)

A paid managed endpoint hosted via OpenRouter.

* **Latency:** ~1905 ms average.
* **Cost:** ~$0.00042 per query call.
* **Function Calling Reliability:** 10/10 (100%) queries correctly routed with valid Pydantic schemas.

---

## Benchmark Results

Evaluation of 10 representative merchant queries across all three candidate providers using `scripts/benchmark_providers.py`:

| Provider | Requests | 2xx Responses | Provider Accepted | Routed KPI (Tool + Schema) | Schema Accuracy | Avg Latency | Avg Cost / Call | Statuses |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Groq (`openai/gpt-oss-20b`)** | 10 | 10 | 100.0% | **100.0% (10/10)** | 100.0% | **1309 ms** | **$0.00005** | 200: 10 |
| **OpenRouter Free (`openrouter/free`)** | 10 | 10 | 100.0% | **20.0% (2/10)** | 25.0% | 4590 ms | $0.0000 | 200: 10 |
| **OpenRouter Llama 3.3 70B (`meta-llama/llama-3.3-70b-instruct`)** | 10 | 10 | 100.0% | **100.0% (10/10)** | 100.0% | 1905 ms | $0.00042 | 200: 10 |

---

## Decision

We select **Groq (`openai/gpt-oss-20b`)** as the primary LLM provider for SokoFlow Phase 3 analytics function calling.

---

## Rationale

1. **Routing Reliability & KPI Compliance:** Groq achieved a 10/10 (100%) score on the benchmark query set, exceeding the Week 1 KPI requirement of ≥ 8/10 routed queries.
2. **Speed & Latency:** Groq yielded an average latency of 1309 ms, which is ~31% faster than OpenRouter Llama 3.3 70B (1905 ms) and ~71% faster than OpenRouter Free (4590 ms). Sub-1.5s latency is essential for WhatsApp user responsiveness.
3. **Cost Efficiency:** At ~$0.00005 per query call, Groq is ~8x cheaper per query than OpenRouter Llama 3.3 70B ($0.00042), keeping monthly operational overhead negligible even at scale.
4. **Schema Integrity:** Combined with structured system prompt instructions for `ReportingPeriod` objects (`period_type` and `relative_period`) and product UUID resolution rules, Groq consistently generates argument payloads that pass strict local Pydantic validation (`ToolValidator.validate_schema`).

---

## Consequences

### Positive

* Meets the Week 1 spec requirement with 10/10 routing accuracy.
* Fast response times (<1.5s avg) for natural WhatsApp conversational interaction.
* Predictable, ultra-low cost structure ($0.00005/call).
* Guarantees non-mutating execution by enforcing server-side schema validation prior to calling service handlers.

### Negative / Tradeoffs

* External API dependency on Groq service availability and rate limits.
* Requires prompt level guidance to ensure nested Pydantic models (such as `ReportingPeriod`) are formatted as objects rather than plain strings.

### Mitigations

* Implement exponential backoff retry handling for HTTP 429 rate-limit responses in `LLMClient`.
* Maintain **OpenRouter (`meta-llama/llama-3.3-70b-instruct`)** as a secondary fallback option in configuration if primary provider outages occur.

---

## References

* Phase 3 Developer Specification (`docs/sokoflow-phase3-spec.pdf`, Week 1 Timeline)
* Benchmark Harness (`scripts/benchmark_providers.py`)
* Full Benchmark Execution Artifact ([benchmark.md](file:///home/paul/sokoflow/benchmark.md))
