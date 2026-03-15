# Fact Observation Predicate Set

Date: 2026-03-15
Status: planned / scaffold-aligned

## Purpose

Define the first **text-grounded observation layer** for Mary-parity fact
intake without exploding the ontology or replacing the existing projection-only
observation types elsewhere in the repo.

The immediate goal is not to model the whole law. It is to cover roughly
80-90% of factual statements in judgments, pleadings, and transcripts with a
small stable predicate set that can sit between:

`source/excerpt/statement -> observation -> event candidate / fact candidate`

## Comparison With Existing Observation Shapes

The repo already contains several observation-like types:

- `CaseObservation`
- `ActionObservation`
- `AlignmentObservation`
- `DecisionObservation`

Those types are **not** the new Mary-parity fact-intake observation layer.

Current interpretation:

- `CaseObservation`, `ActionObservation`, and `AlignmentObservation` are
  domain-specific normalized records for descriptive aggregation.
- `DecisionObservation` is explicitly projection-only and should stay that way.
- The new `ObservationRecord` is a **text-grounded intake record** attached to
  concrete statements/excerpts/sources.

So the new layer complements the existing observation types rather than
replacing them.

## Design Rule

Use:

- few stable predicates
- typed objects
- explicit provenance

Do not:

- create a large legal ontology at intake time
- move doctrinal interpretation into the tokenizer
- use Wikidata as the predicate authority surface

Wikidata/bridge data may enrich the **objects** of observations, not define the
predicate set itself.

## Relation To Existing Semantic Predicate Work

This slice should borrow the repo's existing predicate discipline:

- stable `predicate_key`
- predicate families
- typed downstream objects
- explicit promotion/event-candidate steps after predicate extraction

But it should stay narrower than the existing AU/GWB/transcript semantic
pipelines. This is a **minimal fact-substrate catalog**, not a full semantic
promotion vocabulary.

## Initial Observation Predicate Catalog

### 1. Actor identification

- `actor`
- `co_actor`
- `actor_role`
- `actor_attribute`
- `organization`

### 2. Actions / events

- `performed_action`
- `failed_to_act`
- `caused_event`
- `received_action`
- `communicated`

### 3. Object / target

- `acted_on`
- `affected_object`
- `subject_matter`
- `document_reference`

### 4. Temporal predicates

- `event_time`
- `event_date`
- `temporal_relation`
- `duration`
- `sequence_marker`

### 5. Harm / consequence

- `harm_type`
- `injury`
- `loss`
- `damage_amount`
- `causal_link`

### 6. Legal / procedural predicates

- `alleged`
- `denied`
- `admitted`
- `claimed`
- `ruled`
- `ordered`

## Suggested Next Expansion Set

If the first catalog lands cleanly, the next bounded expansion set is:

- `intent`
- `knowledge`
- `duty`
- `warning`
- `agreement`
- `payment`
- `ownership`
- `authority`
- `location`
- `instrument`

These should remain deferred until the first catalog is operational.

## Storage / Contract Implications

The Mary-parity fact substrate should add a canonical `ObservationRecord` lane
with:

- stable `observation_id`
- `statement_id`, `excerpt_id`, `source_id`
- `predicate_key`
- `predicate_family`
- typed object fields
- explicit provenance
- optional review/abstention status

The first substrate does not need full event assembly yet, but it must make the
next seam explicit:

`statement -> observation -> event candidate / fact candidate`

## Immediate Implementation Stance

Phase 1 should scaffold:

- the observation record/table
- the predicate catalog constants
- schema/example support for `observations[]`
- reporting/projection visibility for observations

It should not yet claim:

- broad automatic extraction over the full predicate set
- doctrinal reasoning
- Bayesian integration
- event-candidate assembly beyond deterministic scaffolding
