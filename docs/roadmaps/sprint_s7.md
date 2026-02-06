# Sprint S7 — Span Authority & Provenance Closure

Thesis: make every interpretive artifact provably traceable to canonical text
without changing semantics or adding reasoning.

## Goals
- Close the TextSpan gap and make span-only real in storage.
- Keep sentences, NRT, and NLP ephemeral.
- Zero ontology expansion.

## Non-goals
- No reasoning or compliance logic.
- No ML.
- No UI expansion beyond debug surfaces.
- No sentence persistence.

## Deliverables

### S7.1 Canonical TextSpan contract
- Define `TextSpan(revision_id, start_char, end_char)`.
- Invariant: text == CST slice.
- Documented and tested.

### S7.2 Bridge legacy artifacts
- Add optional span reference to RuleAtoms and RuleElements.
- Keep existing stored text for backward compatibility.
- Regen test asserting equivalence.

### S7.3 Layer 3 enforcement
- New Layer 3 artifacts must carry `TextSpan`.
- Legacy artifacts allowed but flagged.
- Hard error only on new writes.

### S7.4 Promotion gate hardening
- Promotion requires at least one TextSpan and zero blocking SpanSignalHypotheses.
- Promotion receipts must list span IDs.

## Exit criteria
- Delete all Layer 3 tables and regenerate bit-for-bit.
- Every Layer 3 artifact points to CST.
- No new free-text interpretive artifacts exist.

## Delivery rules
- Tests first, guardrails enforced in CI.
- No ontology changes or semantic normalization.
- Deterministic ordering for all new payloads.
