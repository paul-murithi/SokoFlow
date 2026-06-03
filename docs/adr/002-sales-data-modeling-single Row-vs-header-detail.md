---

# ADR 004: Sales Data Modeling – Single Row vs Header–Detail

**Date:** 2026-06-03
**Status:** Accepted

## Context

We need to decide how to store sales transactions coming from the WhatsApp FSM.

Our users (mostly small-scale vendors like Mama Mbogas and vibanda owners) typically sell items quickly and in small bursts. Most transactions are simple (one item), but occasionally a customer will buy multiple different products in a single visit (for example: tomatoes, onions, and kale together).

The question is whether we optimize for simplicity of interaction or for richer transaction structure.

---

## Options Considered

### Option A: Transaction-per-Item (Current Approach)

**Structure:**
Each row in the `sales` table represents a single product and quantity.

**FSM Flow:**
`START → PRODUCT → QTY → CONFIRM → END`

**Pros:**

* Very simple FSM flow with minimal state
* Low memory overhead in Redis (only one item tracked at a time)
* Fast to implement and easy to debug
* Works well with short, single-item transactions

**Cons:**

* Multi-item purchases require repeating the flow multiple times
* No natural concept of a “receipt” or grouped visit
* Limits reporting (e.g. average basket size per customer visit)

---

### Option B: Header + Line Items (POS Style)

**Structure:**

* `sales` table acts as a receipt header
* `sale_items` stores individual line items per receipt

**FSM Flow:**
`START → PRODUCT → QTY → ADD MORE → CHECKOUT`

**Pros:**

* Supports proper receipt-style grouping of purchases
* Enables better reporting (basket size, visit-level revenue, etc.)
* Easier to apply discounts at cart/receipt level
* Closer to traditional POS systems

**Cons:**

* More complex FSM logic (requires maintaining cart state)
* Higher risk of abandoned or incomplete carts in chat flow
* More moving parts in Redis state management
* Adds overhead that may not be necessary for early version

---

## Decision

We will proceed with **Option A: Transaction-per-Item**.

This aligns with the current Phase 2 Technical Spec and keeps the system intentionally simple.

---

## Rationale

The primary goal at this stage is reliability and ease of use in real-world conditions.

These transactions happen in fast, sometimes chaotic environments. Keeping the flow short and predictable is more important than modeling perfect receipts.

From a usage perspective, the majority of transactions are single-item or near single-item. That makes the added complexity of a cart system hard to justify for the MVP.

Finally, keeping the FSM deterministic makes it significantly easier to test and validate using the existing simulator tooling.

---

## Consequences

* The `sales` table remains the single source of truth for revenue tracking.
* “Visits” or multi-item purchases are not explicitly represented in the data model.
* If needed later, we can reconstruct visit-level grouping in the reporting layer instead of changing the core schema.

---
