# Semantic Rule Slots and Promotion Gates (2026-03-08)

## Purpose
Capture the next bounded semantic-schema refinement for the frozen v1.1 spine:
- keep relations event-scoped
- make rule intent first-class in DB metadata
- keep promotion gates explicit and auditable
- avoid rewriting the current extractors into a new engine all at once

This note defines the intended shared substrate. It does not require a full
extractor migration in the same pass.

## Context
Current semantic v1.1 already preserves the core shape that matters:
- `semantic_event_roles` stores event-local participation/context structure
- `semantic_relation_candidates` stores pre-promotion semantic edge candidates
- `semantic_relations` stores promoted semantic relations
- promoted relations already carry `event_id`, so they are not sentence-global
  facts detached from the decision/action event

What is still missing is a first-class DB description of:
- which rule types exist
- which argument slots a rule expects
- how slots are selected
- what promotion policy a predicate should use

Today that knowledge mostly lives in code and receipt conventions.

## Design Decision
Adopt a slot-based, DB-backed rule metadata layer around the existing semantic
spine.

Chosen scope for this wave:
- add shared metadata tables for rule types, slot definitions, rule slots, and
  promotion policies
- seed those tables with the current bounded semantic families
- keep current extractor code paths intact
- keep current candidate/promotion storage intact
- continue treating `event_role` as participation/context evidence rather than
  as promoted relation output

Not in scope for this wave:
- replacing existing extractor functions with a general rule interpreter
- storing arbitrary parse trees in SQLite
- changing the event-scoped relation model
- broadening canonical ontology kinds

## Core Model

### 1. Event-anchored relations remain mandatory
Legal semantic relations are facts about a specific event in a document, not
free-floating sentence-level triples.

Required interpretation:
- `semantic_event_roles` describe who/what participated in an event
- `semantic_relation_candidates` are candidate relations for that same event
- `semantic_relations` are promoted relations for that same event

This wave does not relax that contract.

### 2. Rules are slot-driven
A rule type declares required slots rather than embedding extraction logic in a
predicate-specific function.

Examples:
- `authority_invocation`
  - `subject`
  - `verb`
  - `object`
- `review_relation`
  - `subject`
  - `verb`
  - `object`
  - optional `forum`
- `actor_role`
  - `actor`
  - `role_marker`
  - `party`

### 3. Selectors stay deterministic
Slot filling remains selector-driven and local to available evidence.

Bounded selector vocabulary for this phase:
- `subject`
- `object`
- `verb`
- `prep_for`
- `nearest_actor`
- `nearest_legal_ref`
- `forum_context`
- `speaker_context`

Selectors are metadata only in this pass; current extractor code can continue
to implement the actual harvesting logic directly until migration is justified.

### 4. Promotion is policy-driven
Rules produce candidate relations. Promotion policies decide whether those
candidates remain:
- `candidate`
- `promoted`
- `abstained`

Promotion policy remains deterministic and receipt-bearing.

## Proposed Shared Metadata Tables

### `semantic_rule_types`
Stores reusable semantic rule families.

Suggested fields:
- `rule_type_key`
- `display_label`
- `description`
- `output_kind`
- `active_v1`
- `pipeline_version`

### `semantic_slot_definitions`
Stores the typed slot vocabulary.

Suggested fields:
- `slot_key`
- `slot_type`
- `description`
- `pipeline_version`

### `semantic_rule_slots`
Stores which slots each rule type expects and how they are filled.

Suggested fields:
- `rule_type_key`
- `slot_key`
- `selector_type`
- `required`
- `slot_order`
- `pipeline_version`

### `semantic_promotion_policies`
Stores predicate-level promotion gate requirements.

Suggested fields:
- `predicate_key`
- `rule_type_key`
- `min_confidence`
- `required_evidence_count`
- `allow_conflict`
- `policy_note`
- `pipeline_version`

## Initial Bounded Families

### Rule families
- `governance_action`
- `executive_action`
- `review_relation`
- `authority_invocation`
- `actor_role`
- `conversational_relation`
- `state_signal`

These are enough to describe the current GWB, AU, and transcript/freeform
predicate families without redesigning the semantic spine.

### Slot vocabulary
- `subject`
- `object`
- `verb`
- `actor`
- `party`
- `role_marker`
- `forum`
- `speaker`
- `state`

Slot typing should stay broad but stable:
- `actor`
- `court`
- `legal_reference`
- `office_holder`
- `party`
- `decision`
- `concept`
- `state`

## Relation Between Metadata and Current Code
This wave should be read as a schema and governance improvement, not as a claim
that the engine is already fully rule-interpreted.

Current posture:
- extractor code may still compute receipts directly
- confidence may still be derived by bounded predicate-specific functions
- promotion now reads shared predicate policy metadata rather than inferring
  promotion status from ad hoc confidence thresholds alone
- emitted candidates and promoted relations should carry rule-family receipts so
  the firing rule type is inspectable without code inference

New expectation after this wave:
- the DB can now say which rule family and promotion policy each predicate
  belongs to
- slot expectations can be inspected without reading the extractor code first
- later migration from predicate-specific logic to a rule interpreter becomes a
  bounded follow-up instead of another schema redesign

## Promotion Gate Requirements
Promotion policies should continue to enforce:
- required slot completeness
- type compatibility
- minimum confidence tier
- minimum evidence count
- conflict blocking when a contradictory predicate is already better supported

This pass only formalizes the first three as shared metadata. Rich conflict
resolution remains deferred until there is concrete corpus pressure.

## Consequences
- The current semantic v1.1 spine remains intact.
- Event anchoring remains the governing anti-corruption rule.
- Rule/slot/policy intent becomes queryable and auditable.
- Current extractors can migrate incrementally instead of all at once.

## Deferred Follow-ups
1. Attach emitted candidates to explicit rule-type usage records or receipts so
   every promoted relation can point back to the rule family without inference.
2. Migrate AU/GWB/transcript predicate confidence functions to consult
   `semantic_promotion_policies` more directly, so confidence derivation and
   promotion policy do not drift.
   Current bounded interpretation:
   - confidence derivation may remain profile-local
   - but it should read shared policy requirements such as
     `required_evidence_count` and `min_confidence`
   - lane-local heuristics should be treated as bounded overlays on top of the
     shared policy, not independent promotion contracts
3. Keep selector execution profile-local for now rather than building a shared
   interpreter in this wave. Revisit only after policy-backed promotion and
   rule-family receipts have stabilized across GWB/AU/transcript lanes.
4. Add conflict-policy metadata only if real contradictory candidate pressure
   appears in the AU/legal or transcript/freeform corpora.
