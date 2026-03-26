# Affidavit Coverage Review

- Version: `affidavit_coverage_review_v1`
- Source kind: `au_checked_handoff_slice`
- Source rows: `3`
- Affidavit propositions: `3`
- Covered: `1`
- Partial: `0`
- Unsupported affidavit propositions: `2`
- Missing-review source rows: `2`
- Related-but-uncovered source rows: `1`
- Related review clusters: `1`
- Normalization-gap source rows: `0`
- Chronology-gap source rows: `0`
- Event-extraction-gap source rows: `0`
- Review-queue-only source rows: `2`
- Evidence-gap source rows: `0`
- Transcript-timestamp hints: `0`
- Calendar-reference hints: `0`
- Procedural-event cues: `1`
- Candidate anchors: `1`
- Provisional structured anchors: `1`
- Provisional anchor bundles: `1`
- Contested source rows: `0`
- Abstained source rows: `0`
- Supported-affidavit ratio: `0.333333`

## Reading

- This is a provenance-first comparison surface, not a legal sufficiency verdict.
- `covered` and `partial` describe segment-aware lexical/source alignment only in this bounded lane.
- `missing_review`, `contested_source`, and `abstained_source` remain operator-review statuses rather than automatic filing conclusions.

## Normalized Metrics

- Review-item statuses: accepted `1`, review_required `2`, held `0`
- Source statuses: accepted `1`, review_required `2`, held `0`
- Dominant primary workload: `queue_pressure`
- Primary workload counts:
  - `structural_pressure` `0`
  - `governance_pressure` `0`
  - `linkage_pressure` `0`
  - `event_or_time_pressure` `0`
  - `evidence_pressure` `0`
  - `normalization_pressure` `0`
  - `queue_pressure` `2`
- Workload presence counts:
  - `structural_pressure` `0`
  - `governance_pressure` `0`
  - `linkage_pressure` `0`
  - `event_or_time_pressure` `0`
  - `evidence_pressure` `0`
  - `normalization_pressure` `0`
  - `queue_pressure` `2`
- Review-required source ratio: `0.666667`
- Candidate signal count: `1`
- Candidate signal density: `0.500000`
- Provisional queue rows: `1`
- Provisional row density: `0.500000`
- Provisional bundles: `1`
- Provisional bundle density: `0.500000`

## Related Review Clusters

- `aff-prop:p1-s1`: 1 related source rows
  Proposition: In House v The King the appellant appealed and the matter was heard by the High Court.
  Dominant workload: review_queue_only
  Recommended next action: advance review queue triage
  Extraction hints: procedural_event_cue (1)
  Candidate anchors: procedural_event_keywords (1)
  Top workload classes: review_queue_only (1)
  Top reasons: review_queue (1)
  Candidate `fact:9d43035cc83c0c08` score `0.4`
  Excerpt: The High Court ruled on the challenge and ordered the matter to proceed.

## Provisional Structured Anchors

- `#1` `fact:9d43035cc83c0c08#anchor:1` procedural_event_keywords -> ordered (score `55`)

## Provisional Anchor Bundles

- `#1` `fact:9d43035cc83c0c08` anchors `1` top-score `55`
