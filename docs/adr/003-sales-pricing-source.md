# ADR 003: Sales Unit Price Source

**Date:** 2026-06-19
**Status:** Accepted

## Context

The Sales domain requires both a `product.price` field and a `sale.unit_price` field.

Products represent the current catalog configuration for a shop. Product prices may change over time as the shopkeeper updates pricing.

Sales represent historical business events and must accurately reflect what occurred at the time the sale was recorded.

A design decision is required regarding the source of `sale.unit_price` during sale creation.

## Options Considered

### Option 1: Accept unit_price from caller

```python
record_sale(
    product_id,
    quantity,
    unit_price,
)
```

The caller provides the unit price, and the sales service stores it directly.

#### Pros

* Supports discounts and negotiated pricing.
* Flexible for future pricing models.

#### Cons

* Introduces multiple sources of truth.
* Allows accidental or malicious price mismatches.
* Requires additional validation and authorization rules.
* Increases complexity for the initial sales workflow.

---

### Option 2: Fetch price from Product

```python
record_sale(
    product_id,
    quantity,
)
```

The sales service loads the product and uses the current product price when creating the sale record.

The value is copied into `sale.unit_price` as a historical snapshot.

#### Pros

* Single source of truth for pricing.
* Simpler API and service design.
* Consistent with current conversational sale flow.
* Reduces risk of incorrect pricing data.
* Easier to test and reason about.

#### Cons

* Does not support discounts or negotiated pricing directly.
* Future pricing flexibility will require additional design work.

## Decision

I Adopted Option 2.

The sales service will fetch the current price from the Product record during sale creation and store that value in `sale.unit_price`.

The caller will not provide a price when recording a sale.

## Rationale

The current project scope focuses on inventory tracking, sales recording, and reporting.

The existing conversational workflow asks the user for a product and quantity only. Price information is derived from the product catalog.

Using Product as the pricing source ensures a single source of truth while preserving historical accuracy through the `sale.unit_price` snapshot.

This approach minimizes complexity while satisfying all current business requirements.

## Consequences

### Positive

* Simpler service interface.
* Consistent reporting and revenue calculations.
* Historical sales remain accurate after future product price changes.
* Reduced validation and security concerns.

### Negative

* Discounts and custom pricing cannot be represented initially.
* Future support for price overrides will require a separate design decision and ADR.

### Future Evolution

If discounting or negotiated pricing becomes a requirement, the sales service may be extended with an explicit override mechanism such as:

```python
record_sale(
    product_id,
    quantity,
    override_price=None,
)
```
