# Current Architecture Baseline

**Last reviewed:** 2026-11-26

This document describes the current implementation at a point in time. It is
not an architecture decision record: consult the [ADR index](../adr/README.md)
for the decisions and rationale behind the design. When this document and the
code disagree, the code is authoritative and this baseline should be corrected.

## Runtime Overview

- FastAPI receives API requests and WhatsApp webhooks.
- Valid, non-duplicate WhatsApp messages are queued for Celery workers.
- The conversation worker runs the FSM and uses Redis-backed conversation
  state.
- PostgreSQL stores shops, products, current inventory balances, and sales.
- Analytics requests use an LLM to propose tool calls. The backend validates
  proposals and executes registered handlers; the model does not directly
  access the database.

The [README architecture section](../../README.md#3-system-architecture--visuals)
contains the request-flow diagrams and local development details.

## Sales and Inventory Records

| Record | Current meaning | Not evidence of |
| --- | --- | --- |
| `sales` row | One recorded product sale, with quantity, a unit-price snapshot, and a database-computed total | A payment being received or settled |
| `inventory.quantity` | SokoFlow's current recorded on-hand balance for a product | A verified physical stock count |

The conversational sale flow deducts inventory and creates a sales row in the
same database transaction. Sales summaries aggregate the sales records.
Inventory add and deduct operations can also change the current balance
independently of a sale. There is no complete inventory movement history,
payment ledger, cash-till record, or reconciliation process.

Consequently, a sales total is recorded sales value, not collected payments;
the inventory balance is recorded stock, not physical-count confirmation.
These boundaries are part of the current MVP, not guarantees that the records
have been reconciled.

## Related Decision Records

- [Sales data model](../adr/002-sales-data-modeling-single%20Row-vs-header-detail.md)
- [Sales price snapshot](../adr/003-sales-pricing-source.md)
- [Low-stock alert delivery](../adr/007-best-effort-low-stock-alert-enqueue.md)
- [Deferred Financial Integrity project](../proposals/financial-integrity.md)
