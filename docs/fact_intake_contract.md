# Fact Intake Contract

Status: v0.1 scaffold

This contract defines the first Mary-parity substrate slice in **SL-native
terms**, with an explicit Mary-compatible projection layered over it.

## Goal

Provide a deterministic sender/receiver chain for:

`source -> excerpt -> statement -> observation -> fact candidate -> contestation/review`

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

5. **Fact sender**
   - derives `FactCandidate` rows from observations and/or statements/excerpts
   - must retain provenance links back to observations/statements/excerpts/sources

6. **Contestation/review sender**
   - records disagreement and review state explicitly
   - must not rewrite canonical source/excerpt/statement/observation text

## Receiver boundaries

1. **Canonical receiver: SQLite read models**
   - `fact_intake_runs`
   - `fact_sources`
   - `fact_excerpts`
   - `fact_statements`
   - `fact_observations`
   - `fact_candidates`
   - `fact_candidate_statements`
   - `fact_contestations`
   - `fact_reviews`

2. **Mary-compatible receiver: workflow projection**
   - `mary.fact_workflow.v1`
   - exposes:
     - facts
     - chronology ordering
     - review queue
     - provenance drill-down handles

3. **Review/debug receiver**
   - deterministic report/bundle outputs over the same read models

## Core records

- `SourceRecord`
- `ExcerptRecord`
- `StatementRecord`
- `ObservationRecord`
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
- existing `CaseObservation` / `ActionObservation` / `AlignmentObservation` /
  `DecisionObservation` shapes are separate projection/aggregation surfaces,
  not replacements for the text-grounded intake observation layer

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
  - deterministic drill-down report including observation visibility
- `build_mary_fact_workflow_projection(...)`
  - Mary-compatible workflow facade over the same read models
