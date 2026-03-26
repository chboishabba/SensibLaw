# Contested Semantic Candidate Schema

Purpose: freeze the minimal candidate object that a contested semantic lane must
emit before canonical promotion.

This is intentionally smaller than the full contested row packet.

## Schema

Version:
- `contested.semantic_candidate.v1`

Mandatory fields:
- `schema_version`
- `candidate_kind`
- `basis`
- `claim_span`
- `response_span`
- `speech_act`
- `polarity`
- `target_component`
- `support_direction`
- `conflict_state`
- `evidentiary_state`

Optional additive fields:
- `modifiers[]`
- `justifications[]`
- `evidence_spans[]`
- `rule_ids[]`

## Constraints

- `candidate_kind` is currently `contested_claim`
- `basis` is one of:
  - `structural`
  - `heuristic`
  - `mixed`
- candidate objects may be rich, but canonical promotion uses only the bounded
  policy-facing subset

## Boundary

This candidate is:
- richer than the promotion gate input contract in raw surface detail
- smaller than the full row packet used inside the review artifact

It exists to stop candidate-shape drift across lanes.

## Current derivation notes

- `target_component` should be binding-first rather than list-order-first.
  Current priority:
  - `characterization` when characterization bindings are present for a
    characterization denial path
  - `time` when time alignment bindings are present
  - otherwise `predicate_text`
- `basis` may be:
  - `structural` when structural sentence evidence is present
  - `mixed` when structural component bindings coexist with heuristic
    justification hints
  - `heuristic` otherwise
