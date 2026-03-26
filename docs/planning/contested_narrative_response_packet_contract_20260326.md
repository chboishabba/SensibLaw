# Contested Narrative Response Packet Contract

This note records the first additive state-model upgrade for the contested-narrative lane.

## Purpose

Move the comparison output away from flat `proposition -> matched excerpt` reading and toward a bounded forensic packet with:

- `duplicate_match_excerpt`
- `best_match_excerpt`
- `best_response_role`
- `response_acts`
- `legal_significance_signals`
- `support_status`
- `support_direction`
- `conflict_state`
- `evidentiary_state`
- `operational_status`
- `semantic_basis`
- `promotion_status`
- `promotion_basis`
- `promotion_reason`
- `semantic_candidate`
- `claim`
- `response`
- `justifications`
- `zelph_claim_state_facts`

This is not yet full legal reasoning. It is a typed intermediate layer.

## Rule Substrate

The contested lane is now structural-first.

Primary semantic derivation in `scripts/build_affidavit_coverage_review.py`
should come from bounded structural signals taken from parsed sentence
dependencies:

- sentence subject
- negation presence
- hedge-verb presence

Current lexical rules are quarantined to auxiliary justification hints only.
They may enrich `justifications` and auxiliary signals, but they must not drive:

- `best_response_role`
- `response.speech_act`
- claim `actor`
- claim-state axes

If structure is insufficient, this lane should abstain conservatively rather
than infer meaning from surface tokens.

## Output Fields

Each contested affidavit proposition row may now carry:

- `duplicate_match_excerpt`
  The near-duplicate allegation/restatement sentence, when one exists in the response block.
- `best_match_excerpt`
  The best later substantive reply sentence surfaced from the same block.
- `best_response_role`
  One of:
  - `dispute`
  - `hedged_denial`
  - `admission`
  - `explanation`
  - `support_or_corroboration`
  - `non_response`
  - `restatement_only`
  - `procedural_frame`
- `response_acts`
  Conservative typed candidate moves such as:
  - `repetition_only`
  - `deny_fact`
  - `deny_characterisation`
  - `hedged_denial`
  - `admit_fact`
  - `justify`
  - `explain_context`
  - `non_response`
  - `scope_limitation`
  - `corroborate_or_ground`
  - `procedural_or_nonresponsive_frame`
- `legal_significance_signals`
  Conservative signal labels such as:
  - `factual_denial`
  - `characterization_dispute`
  - `hedged_denial_signal`
  - `factual_admission`
  - `context_explanation`
  - `evidentiary_grounding_signal`
  - `consent_signal`
  - `authority_or_necessity_signal`
  - `scope_limitation`
- `support_status`
  Current bounded statuses:
  - `textually_addressed`
  - `responsive_but_non_substantive`
  - `substantively_addressed`
  - `evidentially_grounded_response`
  - `unresolved`
- `support_direction`
  Conservative direction over the current packet:
  - `none`
  - `for`
  - `against`
  - `mixed`
- `conflict_state`
  Conservative conflict read:
  - `unanswered`
  - `undisputed`
  - `disputed`
  - `partially_reconciled`
  - `unresolved`
- `evidentiary_state`
  Conservative evidentiary maturity:
  - `unassessed`
  - `unproven`
  - `weakly_supported`
  - `supported`
  - `proven` is reserved and not emitted by this lane
- `operational_status`
  Derived headline only:
  - `claim_only`
  - `claim_with_support`
  - `claim_with_opposition`
  - `disputed_claim`
  - `partially_reconciled_claim`
  - `resolved_but_unproven`
- `semantic_basis`
  Current candidate basis:
  - `structural`
  - `heuristic`
  - `mixed`
- `semantic_candidate`
  Minimal promotion-facing candidate object. See
  `docs/planning/contested_semantic_candidate_schema_20260327.md`.
- `promotion_status`
  Canonical tetralemma promotion state from the central policy gate:
  - `promoted_true`
  - `promoted_false`
  - `candidate_conflict`
  - `abstained`
- `promotion_basis`
  The basis seen by the central promotion gate.
- `promotion_reason`
  Small deterministic explanation from the central promotion gate.
- `claim`
  Span-safe claim packet with:
  - `text_span`
  - `components.predicate_text`
  - optional `components.actor`
  - optional `components.time[]`
  - optional `components.characterization[]`
- `response`
  Span-safe response packet with:
  - `speech_act`
    Fixed basis:
    - `deny`
    - `admit`
    - `explain`
    - `other`
  - `polarity`
  - `target_span`
  - `text_span`
  - `duplicate_text_span`
  - `acts`
  - `modifiers[]`
  - `component_bindings[]`
  - `component_targets[]`
- `justifications`
  Separate typed spans such as:
  - `consent`
  - `authority_or_necessity`
  - `scope_limitation`
  Each packet may also carry:
  - `target_component`
  - `bound_response_span`
  These are currently heuristic lexical hints, not primary semantic drivers.
- `zelph_claim_state_facts`
  Conservative bridge rows for downstream rule/inference work. These are derived
  from the claim-state packet; Zelph should consume them rather than raw text.

## Zelph Bridge

`zelph_claim_state_facts` is the frozen downstream contract for this lane. It is
flat on purpose, so Zelph consumes conservative state facts rather than the full
nested SensibLaw packet.

Each fact row carries:

- `fact_id`
- `fact_kind`
- `proposition_id`
- `best_source_row_id`
- `claim_text_span`
- `claim_actor_span`
- `claim_time_spans`
- `claim_characterization_spans`
- `response_text_span`
- `target_span`
- `duplicate_text_span`
- `response_speech_act`
- `response_polarity`
- `response_modifiers`
- `response_component_targets`
- `response_acts`
- `justification_types`
- `justification_bindings`
- `legal_significance_signals`
- `support_status`
- `coverage_status`
- `support_direction`
- `conflict_state`
- `evidentiary_state`
- `operational_status`
- `semantic_basis`
- `promotion_status`
- `promotion_basis`
- `promotion_reason`

The nested `claim`, `response`, and `justifications` packets remain
SensibLaw-internal row fields. They are the extraction substrate, not the
canonical Zelph bridge.

## Current Promotion Rules

- Duplicate opening allegation sentences are preserved as `duplicate_match_excerpt`.
- In contested mode, surfaced excerpts prefer later non-duplicate sentences inside the same response block.
- `response_acts` and `legal_significance_signals` are candidate labels only.
- lexical justification hints are auxiliary only and do not promote claim-state
  axes on their own.
- `target_component` is now derived binding-first rather than by naive target
  list order.
- canonical truth-bearing promotion is not assigned in this script directly; it
  passes through `src/policy/semantic_promotion.py`.
- Promotion is conservative:
  - no implicit win/loss judgment
  - no doctrinal conclusion
  - ambiguous rows remain reviewable

## Known Limits

- Predicate decomposition is still shallow.
- Actor/action/object/time extraction is not yet canonicalized here.
- `support_status` is still heuristic and should not be treated as a filing conclusion.
- `support_direction`, `conflict_state`, `evidentiary_state`, and `operational_status`
  are conservative packet-level derivations, not court-grade findings.
- `proven` is intentionally unavailable in this lane.

## Next Step

Lift this packet into explicit proposition-component decomposition:

- event/action
- actor/target
- time
- characterization
- consent/authority/scope

Then bind `response_acts` against those components rather than only against sentence-level cues, and expand the Zelph bridge from packet-level state to component-level claim-state facts.
