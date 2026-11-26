# Proposal: SokoFlow Financial Integrity

**Proposal status:** Deferred until after the MVP; detailed scope remains unapproved

**Related decision:** [ADR 025](../adr/025-sokoflow-financial-integrity.md)

## Objective

Extend SokoFlow from recording commercial activity to tracking and reconciling
financial activity, while making the distinction between recorded values and
verified payments or physical counts explicit.

This is a future project proposal. It identifies candidate capabilities and
questions; it does not select a schema, provider API, or implementation
sequence.

## Why This Is Separate from the MVP

The MVP records sales and current inventory balances but does not model
payments, cash-till settlements, a complete inventory movement history, or
reconciliation. Adding these capabilities changes data ownership, transaction
boundaries, support requirements, and failure handling. The current limitation
is documented in the [architecture baseline](../architecture/current-state.md).

## Candidate Scope

### 1. Payment Ledger

- Record payments independently from sales and associate them with the relevant
  sale or outstanding balance.
- Support partial payments, multiple payment methods, and outstanding balances.
- Preserve payment lifecycle and history, including failures, refunds, and
  reversals.
- Store provider or manual references where available.

### 2. Payment Integration

- Evaluate an M-Pesa integration, potentially using Daraja.
- Define explicit transaction states and idempotency before processing
  provider requests or callbacks.
- Handle duplicate, delayed, failed, and reversed provider events without
  duplicating a successful payment.
- Keep provider initiation and confirmation distinct from recording a sale.

### 3. Reconciliation Engine

- Compare expected payments with payment records and available provider or
  operator settlement data.
- Identify unmatched, duplicate, reversed, late, underpaid, and overpaid
  entries.
- Keep discrepancies visible for review; do not silently rewrite sales or
  payment history to make totals agree.

### 4. Inventory Movement Ledger

- Record stock movements with quantity, reason, source, timestamp, and
  responsible actor where known.
- Distinguish sale deductions, restocking, manual adjustments, damage, theft,
  and returns.
- Support recording physical counts and the adjustments made to reconcile
  them with the system balance.
- Define how the current inventory balance relates to the movement history.

### 5. Financial Analytics

Report these as separate measures with explicit inclusion rules:

- Recorded sales value.
- Payments collected.
- Outstanding balances.
- Reconciled revenue.
- Refunds, reversals, and unresolved discrepancies.

## Candidate Design Principles

- A recorded sale is not proof of payment; payment records must be independent
  and auditable.
- A provider callback is an external event, not part of a database transaction;
  durable identifiers and idempotent processing are required.
- A stock balance is a projection of movements, while a physical count is a
  separate observation and reconciliation action.
- Changes that must succeed together inside SokoFlow should have explicit
  database transaction boundaries.
- Corrections should preserve history and identify who or what made the change.
- Existing sales must not be backfilled as paid merely because historical
  payment records do not exist.

## Open Questions Before Planning

- Which manual payment methods are required initially, and which are later
  integrations?
- What sale and payment states are needed for unpaid, partial, cancelled,
  refunded, and reversed transactions?
- What settlement reports or operator-provided inputs will reconciliation
  compare against?
- Who reviews discrepancies, and what correction workflow and audit trail are
  required?
- How should returns affect stock, sales value, payments, and reporting?
- What migration can be performed for existing sales and inventory without
  inventing historical payment or movement facts?
- Which currencies, tax, discounts, and receipt requirements are in scope?

## Candidate Delivery Sequence

The following is a planning hypothesis, not an accepted implementation plan:

1. Define sale, payment, refund, and movement semantics and invariants.
2. Add auditable payment and inventory movement records, initially supporting
   manually recorded payments.
3. Add reconciliation inputs, discrepancy review, and separate reporting.
4. Add M-Pesa integration with idempotent provider event handling.

The sequence and release boundaries should be revisited after scope and
operational requirements are agreed.

## Non-Goals Unless Separately Approved

- Full double-entry accounting or a general ledger.
- Tax filing, payroll, or broad accounting compliance.
- Multiple payment-provider integrations in the first delivery.
- Automatic correction of external settlement or physical-count discrepancies.
