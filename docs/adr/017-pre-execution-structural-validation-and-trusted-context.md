# ADR 017: Pre-Execution Structural Validation and Trusted Context Enforcement

**Date:** 2026-10-30
**Status:** Accepted

---

## Context

In Week 4 Day 2 of Phase 3 AI Analytics, the boundary between model proposals and business operations requires strict hardening. Model proposals are untrusted inputs that may contain:
- Unregistered or hallucinated tool names.
- Multiple simultaneous tool calls.
- Missing required fields, invalid types, or unexpected attributes.
- Attempted injection of tenancy identifiers such as `shop_id`.
- Out-of-bounds or invalid date ranges.

If invalid proposals were allowed to trigger handler execution or repository queries before passing validation:
- Unauthorized shop access or cross-tenant data leakage could occur.
- Database resources would be wasted on invalid requests.
- Business services would be forced to handle structural deserialization errors.

## Decision

We formalize and enforce the strict pre-execution validation order and trusted context boundary in `ToolExecutor`:

1. **Strict Pre-Execution Order:**
   - **Step 1: Resolution:** Look up the requested tool in `ToolRegistry`. Rejects unknown tools immediately without guessing or fuzzy matching.
   - **Step 2: Cardinality & Policy:** Enforce single-tool-call execution; multi-call proposals are rejected as a unit.
   - **Step 3: Structural Validation:** Validate arguments against the tool's registered Pydantic input schema (`extra="forbid"`).
   - **Step 4: Non-Execution Invariant:** Any rejected proposal halts execution immediately and returns a structured failure without invoking the registered handler or touching the database.
   - **Step 5: Trusted Context Injection:** Construct the business invocation using trusted application context (`shop_id`), never model-provided identity arguments.

2. **Prohibition of Model-Supplied `shop_id`:**
   - `shop_id` is prohibited from all AI input schemas and explicitly blocked in `ToolValidator`.
   - Any model proposal containing `shop_id` fails structural validation with a `SchemaValidationError`.
   - The registered handler receives `shop_id` strictly from the validated session/authentication context.

3. **Separation of Structural and Domain Validity:**
   - `ToolExecutor` and input schemas enforce structural validity (types, required fields, date formats, unexpected keys).
   - Backend services remain authoritative for business rules (e.g. date boundaries, product existence, stock thresholds).

## Consequences

- **Guaranteed Isolation:** Cross-tenant access via LLM argument tampering is impossible.
- **Resource Protection:** Business handlers and database transactions are never started for structurally invalid proposals.
- **Auditable Safety:** Unit and integration tests verify side-effect isolation by asserting handler and repository call counts are zero for every invalid proposal.
