# Event Candidate Assembler

Date: 2026-03-15
Status: planned / first-pass implementation target

## Purpose

Make the new observation ontology operational by adding a deterministic
`ObservationRecord -> EventCandidate` assembler.

This is the bridge between:

- text extraction
- chronology / timeline
- fact review
- later legal reasoning

## Design Rule

Events are **derived objects**, not primary source-of-truth records.

Canonical truth remains:

`source -> excerpt -> statement -> observation`

`EventCandidate` rows must always be reconstructable from observations and their
provenance.

## Core Idea

Use a rule-based assembler that performs a bounded relational join over
observations.

Example:

- `actor -> Dr Smith`
- `performed_action -> surgery`
- `acted_on -> plaintiff`
- `event_date -> 2021-05-05`

becomes one derived `EventCandidate`.

## Canonical Storage

## Identity Discipline

Keep two distinct identity layers:

### Structural IDs

Structural IDs should be derived from canonical content only.

Examples:

- excerpt identity from source + anchored span
- statement identity from excerpt + canonical text
- event signature from normalized event fields and evidence shape

Structural identity must stay independent of run metadata.

### Run IDs

Run metadata exists for execution context only:

- `run_id`
- `created_at`
- `pipeline_version`

Run metadata must not change the structural meaning of an extracted record.

### `event_candidates`

- `event_id`
- `run_id`
- `event_type`
- `primary_actor`
- `secondary_actor`
- `object_text`
- `location_text`
- `instrument_text`
- `time_start`
- `time_end`
- `confidence`
- `status`
- `assembler_version`

### `event_attributes`

- `event_id`
- `attribute_type`
- `attribute_value`
- `source_observation_id`
- `confidence`

Used for event details that should not bloat the core table, especially:

- `harm_type`
- `injury`
- `loss`
- `damage_amount`
- `causal_link`
- procedural or legal-state attributes

### `event_evidence`

- `event_id`
- `observation_id`
- `role`
- `confidence`

This is the canonical traceability table for reconstructing an event from
supporting observations.

## Deterministic Assembly Rules

### Minimum creation rule

Create an event candidate when a grouped observation set contains:

- one event-trigger predicate:
  - `performed_action`
  - `failed_to_act`
  - `caused_event`
  - `received_action`
  - `communicated`
- and at least one actor/context anchor:
  - `actor`
  - `co_actor`
  - `organization`
  - or an existing merge-compatible event signature

### Field mapping

- `actor` -> `primary_actor`
- `co_actor` -> `secondary_actor`
- `organization` -> `secondary_actor` when no better counterparty exists
- `performed_action` / `failed_to_act` / `caused_event` / `received_action` /
  `communicated` -> `event_type`
- `acted_on` / `affected_object` / `subject_matter` / `document_reference` ->
  `object_text`
- `event_time` / `event_date` -> `time_start`
- `temporal_relation` / `duration` / `sequence_marker` -> event attributes
- harm/consequence predicates -> event attributes
- legal/procedural predicates -> event attributes, not event-type replacement

### Merge rule

Merge observations into one event candidate when they share a stable signature
over the available subset of:

- trigger predicate/object
- primary actor
- object
- close or equal date/time

The first implementation should stay conservative and deterministic:

- merge only when the signature matches exactly on the populated fields
- do not use embeddings or fuzzy cross-document clustering
- consume normalized observation predicates only, not language-specific raw text

## Status / Lifecycle

Initial statuses:

- `candidate`
- `reviewed`
- `abstained`

Deferred statuses:

- `merged`
- `rejected`

## Explicit Abstention

Abstention must be explicit rather than represented by silent row absence.

Examples:

- observation extracted but no stable event assembled
- insufficient actor/action structure
- contradictory or incomplete evidence bundle

This means the first substrate should preserve status signals such as:

- `captured`
- `candidate`
- `reviewed`
- `uncertain`
- `abstained`
- `no_fact`

## Contestation Handling

Contestation remains observation-first.

Conflicting harm or legal-state observations should attach to the same event
candidate where the underlying action/event is the same. The assembler should
not duplicate the base event solely because an attribute is contested.

## Relation To Existing Facts

For the first slice:

- `FactCandidate` remains available as the broader review object already used by
  the Mary-parity scaffold
- `EventCandidate` becomes the first structured event node derived from
  observations

This means reports should expose both:

- fact candidates
- event candidates plus evidence/attributes

## Immediate Implementation Stance

Phase 1 should implement:

- deterministic event storage tables
- a bounded assembler over stored observations
- report/projection visibility for event candidates
- focused tests for:
  - single-statement assembly
  - multi-statement merge
  - evidence traceability
  - contested attribute attachment

It should not yet implement:

- fuzzy matching
- multilingual event normalization
- cross-run/global event coalescing
- doctrine-aware event typing

## Portability Note

Assembly portability is tracked separately in:

- `SensibLaw/docs/planning/event_assembly_portability_20260315.md`
