# Fact Intake Contract

Status: v0.1 scaffold

This contract defines the first Mary-parity substrate slice in **SL-native
terms**, with an explicit Mary-compatible projection layered over it.

## Goal

Provide a deterministic sender/receiver chain for:

`source -> excerpt -> statement -> observation -> event candidate / fact candidate -> contestation/review`

The canonical receiver is SQLite read models. Human-facing workflow views are
projections over those read models.

## Sender boundaries

1. **Source sender**
   - records bytes/paths/URLs and provenance
   - must not perform semantic extraction

2. **Excerpt sender**
   - records anchored text excerpts from sources
   - must preserve source traceability

3. **Statement sender**
   - records statement-bearing text linked to excerpts
   - may carry speaker/role metadata
   - does not accept/reject facts
   - does not collapse observations directly into doctrinal conclusions

4. **Observation sender**
   - emits text-grounded `ObservationRecord` rows from statements/excerpts
   - uses a small stable predicate set with typed objects
   - must remain provenance-linked to statements/excerpts/sources
   - may abstain when no supported predicate/object extraction is available
   - may use language/jurisdiction-specific dictionaries and mappings, but must
     emit normalized observation predicates for downstream assembly

5. **Fact sender**
   - derives `FactCandidate` rows from observations and/or statements/excerpts
   - must retain provenance links back to observations/statements/excerpts/sources

6. **Event assembler**
   - deterministically derives `EventCandidate` rows from stored observations
   - must be reconstructable from observation evidence
   - must not replace observations as the canonical source of truth
   - should remain conservative and merge only on stable explicit signatures
   - must consume normalized predicates rather than raw language-specific text

7. **Contestation/review sender**
   - records disagreement and review state explicitly
   - must not rewrite canonical source/excerpt/statement/observation/event text

## Receiver boundaries

1. **Canonical receiver: SQLite read models**
   - `fact_intake_runs`
   - `fact_sources`
   - `fact_excerpts`
   - `fact_statements`
   - `fact_observations`
   - `event_candidates`
   - `event_attributes`
   - `event_evidence`
   - `fact_candidates`
   - `fact_candidate_statements`
   - `fact_contestations`
   - `fact_reviews`
   - semantic sidecar tables:
     - `semantic_class_vocab`
     - `semantic_relation_vocab`
     - `semantic_rule_vocab`
     - `policy_vocab`
     - `entity_class_assertions`
     - `entity_relations`
     - `policy_outcomes`
     - `semantic_refresh_runs`

2. **Mary-compatible receiver: workflow projection**
   - `mary.fact_workflow.v1`
   - exposes:
     - facts
     - chronology ordering
     - review queue
     - provenance drill-down handles

3. **Review/debug receiver**
   - deterministic report/bundle outputs over the same read models
   - bounded operator views:
     - `intake_triage`
     - `chronology_prep`
     - `procedural_posture`
     - `contested_items`
   - bounded read-only workbench payload over the same persisted run

## Core records

- `SourceRecord`
- `ExcerptRecord`
- `StatementRecord`
- `ObservationRecord`
- `EventCandidate`
- `FactCandidate`
- `ContestationRecord`
- `FactReviewRecord`

## Current scaffold rules

- canonical naming stays SL-native
- Mary is the workflow benchmark, not the canonical vocabulary
- chronology is present but lightweight in phase 1
- contestation is thin but real in phase 1
- no tokenizer changes are permitted for this slice
- external refs remain linked enrichments, not identity rewrites
- observation predicates should be stable and few; objects can be richer
- event candidates are derived, not canonical source-of-truth objects
- structural identity must stay separate from run metadata
- abstention must be explicit rather than inferred from missing rows
- ontology-bearing semantics should not live long-term in `provenance_json`
- compatibility arrays like `signal_classes` / `source_signal_classes` are projection outputs, not canonical storage
- existing `CaseObservation` / `ActionObservation` / `AlignmentObservation` /
  `DecisionObservation` shapes are separate projection/aggregation surfaces,
  not replacements for the text-grounded intake observation layer

## Semantic normalization layer

The semantic layer is additive beside the raw fact-intake tables.

1. Observed base data
   - stays in the core read-model tables above
2. Controlled classifications
   - persisted as normalized rows in `entity_class_assertions`
3. Inference results
   - also persisted in `entity_class_assertions`, distinguished by origin/rule
4. Operational consequences
   - persisted in `policy_outcomes`

Cross-entity semantics such as authority-boundary relations belong in
`entity_relations`, not flattened tags.

## Composed candidate normalization boundary

Composed candidate nodes are the explicit bridge between the structural,
source-anchored substrate and downstream promoted or interpretive outputs.
They are normalized derivations, not canonical source rows, and they must stay
reconstructable from the preserved evidence chain.

- canonical contract surface: `sl.composed_candidate_node.v1`
- purpose: group source-backed structural signals into a reusable candidate
  node before any promotion or interpretive reuse
- required boundary rules:
  - keep source anchoring intact
  - preserve normalized `kind` / `value` semantics without rewriting the
    underlying substrate
  - treat the node as fail-closed until admissibility explicitly returns
    `promote`, `audit`, or `abstain`
  - do not collapse candidate normalization into the final review or
    projection surfaces
- placement:
  - above raw fact-intake observation and event derivation
  - below promoted facts, review projections, and interpretive overlays

The lexical Zelph graph remains derived/materialized rather than normalized
into OLTP token tables.

## Identity / run distinction

- structural IDs are content-derived and deterministic
- run IDs capture execution context only
- provenance and timestamps must not rewrite structural identity

## Explicit status semantics

The first fact substrate should preserve explicit status values rather than
using absence as meaning.

Expected status families include:

- statements:
  - `captured`
  - `abstained`
- observations:
  - `captured`
  - `uncertain`
  - `abstained`
- facts:
  - `candidate`
  - `reviewed`
  - `uncertain`
  - `abstained`
  - `no_fact`
- events:
  - `candidate`
  - `reviewed`
  - `abstained`

## Initial observation predicate catalog

Predicate families for the first fact-substrate:

- actor identification:
  - `actor`
  - `co_actor`
  - `actor_role`
  - `actor_attribute`
  - `organization`
- actions / events:
  - `performed_action`
  - `failed_to_act`
  - `caused_event`
  - `received_action`
  - `communicated`
- object / target:
  - `acted_on`
  - `affected_object`
  - `subject_matter`
  - `document_reference`
- temporal:
  - `event_time`
  - `event_date`
  - `temporal_relation`
  - `duration`
  - `sequence_marker`
- harm / consequence:
  - `harm_type`
  - `injury`
  - `loss`
  - `damage_amount`
  - `causal_link`
- legal / procedural:
  - `alleged`
  - `denied`
  - `admitted`
  - `claimed`
  - `ruled`
  - `ordered`

See also:
- `SensibLaw/docs/planning/fact_observation_predicate_set_20260315.md`

## Implemented phase-1 helpers

- `build_fact_intake_payload_from_text_units(...)`
  - deterministic sender helper from existing `TextUnit` carriers
  - does not attempt broad automatic observation extraction yet
- `persist_fact_intake_payload(...)`
  - persists the canonical read-model family
- `build_fact_intake_report(...)`
  - deterministic drill-down report including observation and event visibility
- `build_mary_fact_workflow_projection(...)`
  - Mary-compatible workflow facade over the same read models
- `build_fact_review_run_summary(...)`
  - canonical review queue / contested / chronology triage summary
- `build_fact_review_operator_views(...)`
  - bounded operator-facing slices for intake, chronology, procedure, and contested review
- `build_fact_review_workbench_payload(...)`
  - read-only workbench contract over a persisted fact-review run

## Acceptance harness stance

- parity should be judged against explicit user stories, not only schema shape
- wave-1 legal parity should be gated by a canonical fixture manifest and a
  deterministic batch runner over persisted transcript/AU fact-review runs
- acceptance may use a mixed evidence base:
  - curated real runs where available
  - synthetic seeded runs where a role/story gap still needs deterministic coverage
- acceptance reports should classify each story as:
  - `pass`
  - `partial`
  - `fail`
- the harness is descriptive only; it does not mutate the underlying substrate
- acceptance reports should carry failed-check IDs and bounded gap tags so the
  next patch loop is backlog-driven rather than ad hoc

## Current legal-operator review stance

- review surfaces should distinguish:
  - party assertion
  - procedural outcome
  - later annotation / note
- chronology should distinguish:
  - dated events
  - approximate/relative chronology
  - undated events
  - facts with no assembled event
- workbench/operator views may add grouping and filtering over these signals,
  but they must remain projections over the persisted run rather than a second
  backend

## Event-candidate assembly stance

- use a deterministic assembler over observations
- create event candidates from bounded trigger predicates plus actor/context
  anchors
- keep harm and legal/procedural rows as event attributes where appropriate
- keep contestation observation-first even when multiple observations attach to
  one event
- keep language/jurisdiction variation in normalization packs and concept
  mappings rather than the assembler logic

See also:
- `SensibLaw/docs/planning/event_candidate_assembler_20260315.md`
- `SensibLaw/docs/planning/event_assembly_portability_20260315.md`
