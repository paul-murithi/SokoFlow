# ADR 025: Defer Financial Integrity Until After the MVP

**Date:** 2026-11-26
**Decision status:** Accepted

## Context

The MVP records sales and current inventory balances, but it does not record
payments, cash-till settlement, a complete inventory movement history, or
reconciliation. Adding these capabilities would broaden the MVP and introduce
additional financial and operational failure modes.

The current sales and inventory records must not be presented as proof of
collected payment or verified physical stock. See the [current architecture
baseline](../architecture/current-state.md) for what the application records
today.

## Decision

Defer the SokoFlow Financial Integrity project until after the MVP. Keep the
MVP focused on recording commercial activity, and distinguish recorded sales
value from collected payments in product language and reporting.

The future project's candidate scope and open design questions are recorded in
the [SokoFlow Financial Integrity proposal](../proposals/financial-integrity.md).
This decision does not approve a payment provider, data model, delivery
sequence, or detailed reconciliation policy.

## Rationale

Payment capture, settlement matching, and inventory movement auditability
require explicit domain rules and reliable handling of retries, reversals, and
discrepancies. They should be designed as a coherent follow-up project rather
than introduced piecemeal into the MVP.

## Consequences

- The MVP cannot determine from its own records whether a sale was paid or a
  till balanced.
- The recorded inventory balance is not a verified physical count and does
  not explain every movement.
- Existing sales analytics represent recorded sales value, not collected or
  reconciled revenue.
- Historical sales must not later be treated as paid merely because payment
  records did not yet exist.
