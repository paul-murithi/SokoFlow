# ADR 024: Evaluation-Only Token Throttling and Bounded Provider Retries

**Date:** 2026-11-22
**Decision status:** Accepted

## Context

The shared `LLMClient` is used by production analytics and local evaluation runs.
Provider retry behavior belongs to that transport boundary, but an in-memory
token bucket cannot enforce a provider-wide limit across processes or replicas.
Applying the evaluation bucket to every client instance would therefore both
throttle production unexpectedly and provide a misleading guarantee about
provider-wide usage.

The provider's `Retry-After` header is externally supplied and may be malformed,
non-finite, or excessively long. Provider error bodies can also echo request
content and should not be written to logs or propagated in exceptions.

## Decision

- Keep estimated-token throttling in the evaluation harness only. The in-memory
  bucket is a best-effort pacing aid for a local run, not a production or
  cross-worker rate limit.
- Continue relying on the per-shop daily quota and per-call token ceiling for
  v1 production exposure controls. Add a shared provider limiter only if measured
  production usage demonstrates that it is needed.
- Retry HTTP 429 responses only. Parse numeric `Retry-After` values and HTTP
  dates, reject invalid/negative/non-finite values in favor of exponential
  backoff with jitter, and cap each wait at 60 seconds.
- Bound the total provider request, including retries and backoff, with a
  60-second overall deadline. Keep the per-attempt HTTP timeout as a separate
  lower-level transport guard.
- Do not retry transport errors or other HTTP statuses in v1. Additional retry
  classes can amplify provider outages and should be introduced only with a
  separate bounded policy.
- Close locally owned HTTP clients in a `finally` block and do not close
  injected clients.
- Keep provider error messages limited to status codes so echoed request data
  cannot leak into logs or downstream error reporting.
- Classify provider and infrastructure failures separately in evaluation
  results; they remain failed turns in aggregate pass rates but are identifiable
  as non-model failures.

## Consequences

- The evaluation token bucket does not affect production request latency.
- Production replicas may collectively exceed a provider's TPM allowance; v1
  does not claim to enforce a global provider limit.
- A provider request cannot spend longer than the configured overall deadline
  in HTTP attempts and retry waits combined.
- Evaluation reports preserve infrastructure failures as failed turns while
  making them distinguishable from model-quality failures.
