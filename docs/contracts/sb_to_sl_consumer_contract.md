# SB -> SL Consumer Contract v0.1

## Purpose
Define the bounded surfaces that SensibLaw may consume from StatiBaker for
workflow, provenance, and compliance evaluation without upgrading SB state into
semantic or legal truth.

## Allowed SB fields for SL consumption
- `compiled_state_id`
- `compiled_state_version`
- `follow_obligation`
- `unresolved_pressure_status`
- `lineage_refs`
- `provenance_refs`
- `source_artifact_refs`
- `observer_overlay_refs`
- `casey_observer_refs`

## Allowed interpretation by SL
SensibLaw may treat these fields as:
- workflow state
- follow-up signal
- provenance/context reference
- compliance evidence input

SensibLaw may not treat these fields as:
- semantic truth
- legal conclusion
- factual authority
- canonical ontology input without independent grounding

## Casey-derived refs through SB
Casey-derived data may pass through SB to SL only as:
- operation refs
- build refs
- workspace refs
- receipt hashes
- lineage refs

Casey mutable state, candidate graphs, or free-form summaries are forbidden as
SL semantic inputs.

## Compliance use
SL may evaluate SB and Casey refs against bounded control profiles only as
evidence of:
- process traceability
- execution integrity
- follow-up pressure
- workflow completion state

SL must emit one of:
- `satisfied`
- `not_satisfied`
- `insufficient_evidence`
- `not_applicable`

per control group, with cited evidence.

## Abstention rule
If the available evidence does not support a grouped control assessment, SL
must emit `insufficient_evidence`.

## Explicitly forbidden payloads
- raw `state`, `events`, `threads`, `activity_ledger`, or `drift` payloads
- semantic summaries treated as authority
- OCR-derived belief without independent grounding
- Casey mutable workspace payloads or candidate graphs
