# ADR 006: Handle Large Low-Stock Result Sets in Daily Reports

**Date:** 2026-09-13
**Status:** Accepted

## Context

The daily report includes products that are currently considered low on stock for a given shop.

The current implementation retrieves all products satisfying:

```text
inventory.quantity <= inventory.low_stock_threshold
```

and includes the resulting products in the daily report.

This is sufficient for the current MVP and learning objectives. However, a shop may eventually have a large number of products that simultaneously meet the low-stock condition. Including every matching product in the PDF could make the report unnecessarily large and reduce its usefulness as a daily summary.

The current project is focused on shipping the MVP while building production-grade engineering skills. There is therefore no immediate requirement to introduce pagination, result limits, or a separate inventory report solely to address a potential large result set.

---

## Options Considered

### Option A: Return All Low-Stock Products

**What it is:**
Query and include every product in the shop whose current inventory quantity is at or below its low-stock threshold.

**Pros:**

* Provides complete low-stock information.
* Simple to implement and understand.
* No products are omitted from the report.
* Appropriate for the current MVP scope.

**Cons:**

* The PDF could become very large if many products are low on stock.
* A long low-stock section could reduce the usefulness of the daily summary.
* Report generation and rendering may become more expensive as the number of products grows.

---

### Option B: Limit or Summarize Low-Stock Products in the Daily Report

**What it is:**
Introduce business rules for handling large low-stock result sets, such as displaying only a limited number of products, summarizing the remaining count, or moving the complete list to a dedicated inventory report.

**Pros:**

* Keeps the daily report concise.
* Improves readability for shops with many products.
* Separates daily operational summaries from potentially large inventory datasets.
* Provides a path for scaling the reporting feature.

**Cons:**

* Some low-stock products would not appear directly in the daily report.
* Requires additional business rules and product decisions.
* May require a separate mechanism for users to access the complete low-stock list.
* Adds complexity that is not currently necessary for the MVP.

---

## Decision

**Chosen option:** Option A: Return All Low-Stock Products

---

## Rationale

The current MVP will return all products that meet the low-stock condition.

This provides the simplest and most complete implementation while the project is focused on learning and shipping the MVP rather than optimizing for an established production-scale user base.

Option B is intentionally deferred because the potential problem is dependent on future product scale and reporting requirements. Introducing limits or summarization now would add business rules before there is evidence that they are necessary.

The current implementation therefore accepts the possibility that the low-stock section could become large in the future in exchange for keeping the MVP simple and complete.

---

## Consequences

### Positive

* The daily report contains the complete current low-stock picture.
* The implementation remains simple.
* No low-stock products are hidden or arbitrarily excluded.
* Avoids premature optimization during the MVP phase.

### Negative / Tradeoffs

* Daily PDFs may become unnecessarily large for shops with many low-stock products.
* The low-stock section may eventually dominate the daily report.
* Report generation and PDF rendering may require additional optimization at larger scales.

### Future Work

* Define business rules for handling large low-stock result sets.
* Consider limiting the number of products displayed in the daily report.
* Consider displaying a summary such as “15 additional products are low on stock.”
* Consider providing the complete low-stock inventory through a dedicated inventory report or another interface.
* Revisit this decision once realistic usage or user feedback demonstrates that large low-stock lists are a problem.

---

## Notes

The current query intentionally remains:

```text
WHERE inventory.quantity <= inventory.low_stock_threshold
```

The low-stock section represents the shop's **current inventory state**, rather than only products sold during the reported day.

This ADR records a consciously accepted MVP limitation rather than an immediate implementation requirement.
