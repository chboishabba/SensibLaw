# No Surface-Semantic Mapping Policy

Purpose: prevent contested-claim and similar reasoning lanes from deriving
semantic meaning directly from surface strings.

## Core rule

Semantic values must be derived from:
- span/provenance substrate
- structural parsing or other declared structural analysis
- explicit rule functions over structure

Semantic values must not be derived directly from:
- semantic cue lists
- regex-to-meaning mappings
- actor/entity whitelists
- domain vocabulary used as primary classification logic

In short:

```text
semantic_value = f(structure, spans, closed_class_rules)
```

Not:

```text
semantic_value = f(surface_tokens)
```

## Allowed primitives

1. Span-based substrate
- exact text
- offsets
- provenance

2. Structural extraction
- dependency structure
- subject / root / negation
- entity spans such as dates

3. Explicit rule functions
- deterministic
- inspectable
- operate on parsed or otherwise structured inputs

4. Small closed-class lexical sets
- grammar/negation terms
- epistemic/hedge verbs
- similar bounded language classes

## Forbidden patterns

1. Semantic cue lists

```python
("consent", "email", "record", "care")
```

2. Regex mapped directly to semantic labels

```python
r"\\bi do not feel\\b" -> "hedged_denial"
```

3. Actor/entity whitelists

```python
("Johl", "John", "The respondent")
```

4. Domain vocabulary as primary classification logic

```python
"consent" -> justification -> speech_act / claim_state
```

## Contested-lane application

For `scripts/build_affidavit_coverage_review.py`:
- `response.speech_act` and response-role classification must be structural-first
  and may abstain to `other` / `non_response` when structure is insufficient.
- claim `actor` extraction must be structural-only; fallback actor whitelists are
  forbidden.
- lexical hints may exist only in a quarantined heuristic layer.

## Heuristic quarantine

Lexical heuristics are allowed only when all of the following hold:
- they are explicitly named as heuristic
- they are bounded to an auxiliary surface
- they do not determine primary `speech_act`
- they do not determine claim-state axes

Current temporary exception:
- contested-lane justification hints remain lexical and heuristic-only
- they may enrich `justifications` / auxiliary signals
- they must not drive `speech_act`, `support_direction`, `conflict_state`, or
  `evidentiary_state`

## Governance

Required guardrails:
- a test must fail if contested-lane lexical rules are used for `speech_act` or
  `actor`
- a test must fail if lexical justification hints start driving claim-state axes
- new enum values require explicit lattice-level justification

## Central promotion gate

Canonical semantic truth must pass through a central promotion gate.

Current first implementation:
- `src/policy/semantic_promotion.py`

The gate emits one tetralemma status only:
- `promoted_true`
- `promoted_false`
- `candidate_conflict`
- `abstained`

Candidate semantics may be richer, but canonical promotion must be derived from:
- structural basis
- bounded claim-state inputs

and must not be assigned directly in extraction code.

Current lane coverage:
- contested-claim rows in `scripts/build_affidavit_coverage_review.py`
- semantic-relation rows in `src/gwb_us_law/semantic.py`
- AU semantic reports inherit the same relation-candidate policy surface via
  `src/au_semantic/semantic.py`

## Truth-bearing fields

Truth-bearing fields are any fields that assert canonical semantic state for a
claim in a way downstream code could treat as truth-like.

Current contested-lane truth-bearing fields:
- `promotion_status`
- `support_direction`
- `conflict_state`
- `evidentiary_state`
- `operational_status`

Current contested-lane non-truth-bearing fields:
- `coverage_status`
- `speech_act`
- `response_acts`
- `legal_significance_signals`
- `best_response_role`
- `justifications`

Current semantic-relation lane truth-bearing fields:
- legacy lane-local `promotion_status`
- central `canonical_promotion_status`

Current semantic-relation lane non-truth-bearing fields:
- `semantic_basis`
- `semantic_candidate`
- `receipts`
- `confidence_tier`

Current mission-observer / actual-mapping lane boundary:
- these surfaces are operational-state only, not canonical truth
- examples: observer `status`, observer `confidence`, actual-mapping `status`,
  actual-mapping `confidence_tier`, mission-lens recommendation fields
- they may drive workflow allocation and review posture
- they must not be treated as truth-bearing semantic promotion outputs

Rule:
- truth-bearing fields must be assigned from claim-state derivation or the
  central promotion gate
- non-truth-bearing fields must not be treated as canonical truth in CI or
  downstream policy

## Enforcement map

- Guard test: `tests/test_contested_surface_semantic_policy.py`
- Policy tests: `tests/policy/test_semantic_promotion.py`
- Contested lane: `scripts/build_affidavit_coverage_review.py`
- Relation lane: `src/gwb_us_law/semantic.py`
- Observer-state guard: `tests/test_transcript_semantic.py`
- Packet contract note:
  `docs/planning/contested_narrative_response_packet_contract_20260326.md`
