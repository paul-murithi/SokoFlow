# ADR 016: Analytics Semantic Ambiguity and Clarification

**Date:** 2026-10-28
**Status:** Accepted

---

## Context

The analytics model can receive an ambiguous follow-up such as:

> "What were my sales today?"
> "What about the other?"

The model may infer a period and propose a valid analytics tool call even when
the user's intended meaning is unclear. The current backend validates tool
identity, argument structure, and domain constraints, but it does not verify
that the proposed call semantically matches the user's intended meaning.

The normalized LLM response contract supports either tool calls or text, but
the orchestration flow currently treats a response without tool calls as
`NO_ANALYTICS_INTENT`. It does not expose a dedicated clarification outcome.

## Decision

For v1, accept the residual risk of semantically incorrect but structurally
valid tool calls. Do not introduce a separate semantic-validation, confidence,
or ambiguity-detection subsystem.

The existing validation and execution boundaries remain responsible for
rejecting invalid tools, malformed arguments, and domain failures. A tool call
that passes those checks may execute even if the user's natural-language
question was ambiguous.

## Consequences

* The system remains small and deterministic at the backend boundary.
* Ambiguous follow-ups may occasionally receive an answer for the wrong
  interpretation.
* Existing follow-up context and bounded retry behavior are unchanged.
* Tool-call validity must not be treated as proof of semantic correctness.

## Future Revisit

If the LLM contract provides a supported clarification signal, add a dedicated
clarification outcome and presentation path rather than building a general
semantic-verification layer by default.

That future change should define:

* how the model signals that clarification is required;
* whether clarification preserves the prior analytics context;
* how clarification differs from no analytics intent;
* whether the backend should enforce any narrow, measurable safeguards.
