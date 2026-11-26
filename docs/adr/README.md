# Architecture Decision Records

ADRs are the durable history of consequential architecture decisions. They
capture why an option was selected, not a complete description of today's
system or a backlog of possible improvements.

## How to Read Status

**Decision status** describes the decision:

- **Accepted** — the decision was made. This does not claim that all related
  implementation work is complete or that the code has not since drifted.
- **Proposed** — a decision is under review and has not been approved.
- **Superseded** — a later ADR replaces this decision; retain the record and
  link to its successor.
- **Rejected** — the option was explicitly considered and not selected.

Implementation progress belongs in issues, pull requests, or the relevant
project proposal; do not overload the ADR decision status with delivery state.
The [current architecture baseline](../architecture/current-state.md) describes
the current behavior. Future projects and unresolved design work belong in
[proposals](../proposals/README.md).

Accepted ADRs are retained as history. Correct factual errors and broken links,
but record a changed decision in a new ADR and mark the old one superseded
rather than rewriting the decision history.

## Decision Index

### Core Platform and Business Records

| ADR | Decision | Status |
| --- | --- | --- |
| [001](./001-redis-for-sessions.md) | Use Redis for FSM session storage | Accepted |
| [002](./002-sales-data-modeling-single%20Row-vs-header-detail.md) | Model sales as single-item transaction rows | Accepted |
| [003](./003-sales-pricing-source.md) | Snapshot the product price on each sale | Accepted |
| [004](./004-last-write-for-updates.md) | Use Last Write Wins for product updates | Accepted |
| [005](./005-sql-file-workflow-for-handwritten-queries.md) | Keep handwritten analytical SQL in query files | Accepted |
| [006](./006-handle-large-low-stock-result-sets-in-daily-reports.md) | Return all low-stock products in daily reports | Accepted |
| [007](./007-best-effort-low-stock-alert-enqueue.md) | Enqueue low-stock alerts best-effort after commit | Accepted |
| [008](./008-define-previous-comparison-period-semantics.md) | Compare with the previous equivalent calendar period | Accepted |

### Conversational Analytics

| ADR | Decision | Status |
| --- | --- | --- |
| [009](./009-llm-provider-selection-for-analytics-function-calling.md) | Select the analytics function-calling provider | Accepted |
| [010](./010-llm-provider-boundary-and-normalized-contract.md) | Normalize provider interaction behind `LLMClient` | Accepted |
| [011](./011-toolexecutionresult-envelope-and-execution-boundary.md) | Separate tool execution from its result envelope | Accepted |
| [012](./012-analytics-routing-inside-idle-intent-dispatch.md) | Route analytics from IDLE intent dispatch | Accepted |
| [013](./013-analytics-follow-up-context-arguments.md) | Persist validated semantic arguments for follow-ups | Accepted |
| [014](./014-failure-semantics-and-bounded-repair-policy.md) | Bound repair and distinguish analytics failures | Accepted |
| [015](./015-analytics-context-preservation-across-failures.md) | Preserve the last successful analytics context | Accepted |
| [016](./016-analytics-semantic-ambiguity-and-clarification.md) | Accept residual semantic ambiguity risk in v1 | Accepted |
| [017](./017-pre-execution-structural-validation-and-trusted-context.md) | Validate tool proposals before execution and inject trusted context | Accepted |
| [018](./018-count-every-analytics-processing-message.md) | Count every analytics-processing message against quota | Accepted |
| [019](./019-fixed-window-and-per-shop-analytics-quota.md) | Use a fixed daily per-shop analytics quota | Accepted |
| [020](./020-post-call-provider-usage-accounting.md) | Account for provider usage after each call | Accepted |
| [021](./021-bounded-analytics-provider-repair-exposure.md) | Reuse the bounded repair policy for provider exposure | Accepted |
| [022](./022-single-finalized-analytics-interaction-record.md) | Persist one finalized record per analytics interaction | Accepted |

### Evaluation, Provider Reliability, and Product Scope

| ADR | Decision | Status |
| --- | --- | --- |
| [023](./023-separate-provider-benchmarking-from-application-integration.md) | Keep provider evaluation distinct from integrated benchmarking | Accepted |
| [024](./024-evaluation-only-token-throttling-and-bounded-provider-retries.md) | Restrict evaluation throttling to evaluation and bound provider retries | Accepted |
| [025](./025-sokoflow-financial-integrity.md) | Defer the Financial Integrity project until after the MVP | Accepted |

## Writing or Updating an ADR

Create an ADR when a consequential choice has been made or needs review. Keep
it focused on one decision and include its context, considered options,
decision, rationale, and consequences. Do not use an ADR as:

- A current-state system inventory — update the architecture baseline.
- An unapproved future-work proposal — add or update a proposal.
- An implementation checklist — track the work in an issue or pull request.

For minor corrections, fix the record in place. For a changed decision, add a
new numbered ADR and mark the old decision **Superseded** with a link to its
successor.
