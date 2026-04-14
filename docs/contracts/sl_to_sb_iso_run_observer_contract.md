# SL -> SB ISO Run Observer Contract v0.1

## Purpose
Define the bounded observer overlay that SensibLaw may emit to StatiBaker so
SB can track ISO-style run state, outputs, and follow pressure without
ingesting ISO meaning.

## Allowed SL fields for SB consumption
- `run_id`
- `artifact_refs`
- `output_refs`
- `follow_obligation`
- `unresolved_pressure_status`
- `lineage_refs`
- `source_artifact_refs`
- optional `casey_observer_refs`

These travel inside a reference-heavy observer overlay with:
- `activity_event_id`
- `annotation_id`
- `provenance`
- `state_date` or `sb_state_id`
- `observer_kind = sensiblaw_iso_run_v1`

## Allowed interpretation by SB
StatiBaker may treat these fields as:
- run/workflow state
- output lineage
- follow-up pressure
- observer provenance

StatiBaker may not treat these fields as:
- semantic truth
- legal interpretation
- canonical state rewrite authority
- control-plane instructions

## Casey-derived refs through SL
Casey-derived data may appear only as:
- workspace refs
- operation refs
- build refs
- tree ids
- selection digests
- receipt hashes

They remain observer/provenance refs only.

## Explicitly forbidden payloads
- raw semantic summaries treated as authority
- parser/envelope internals as mandatory consumer inputs
- mutable Casey workspace payloads or candidate graphs
- OCR-derived belief as authority
- raw SB state/event/thread payloads echoed back into SB
