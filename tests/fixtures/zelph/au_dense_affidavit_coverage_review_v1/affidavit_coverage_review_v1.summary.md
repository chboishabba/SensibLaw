# Affidavit Coverage Review

- Version: `affidavit_coverage_review_v1`
- Source kind: `au_dense_overlay_slice`
- Source rows: `24`
- Affidavit propositions: `3`
- Covered: `2`
- Partial: `0`
- Unsupported affidavit propositions: `1`
- Missing-review source rows: `21`
- Related-but-uncovered source rows: `3`
- Related review clusters: `1`
- Normalization-gap source rows: `0`
- Chronology-gap source rows: `21`
- Event-extraction-gap source rows: `21`
- Review-queue-only source rows: `0`
- Evidence-gap source rows: `21`
- Transcript-timestamp hints: `13`
- Calendar-reference hints: `6`
- Procedural-event cues: `15`
- Candidate anchors: `34`
- Provisional structured anchors: `34`
- Provisional anchor bundles: `21`
- Contested source rows: `0`
- Abstained source rows: `0`
- Supported-affidavit ratio: `0.666667`

## Reading

- This is a provenance-first comparison surface, not a legal sufficiency verdict.
- `covered` and `partial` describe segment-aware lexical/source alignment only in this bounded lane.
- `missing_review`, `contested_source`, and `abstained_source` remain operator-review statuses rather than automatic filing conclusions.

## Related Review Clusters

- `aff-prop:p2-s1`: 3 related source rows
  Proposition: One of the critical features of the original Civil Liability Act, Part 1A, was that it sharpened the distinction between intentional wrongs and negligence.
  Dominant workload: chronology_gap
  Recommended next action: promote existing event/date cues into structured anchors
  Extraction hints: transcript_timestamp_hint (2), calendar_reference_hint (1), procedural_event_cue (1)
  Candidate anchors: transcript_timestamp_window (2), calendar_reference (1), procedural_event_keywords (1)
  Top workload classes: chronology_gap (3), event_extraction_gap (3), evidence_gap (3)
  Top reasons: chronology_undated (3), event_missing (3), missing_date (3)
  Candidate `fact:70d7cdc9317e1dd1` score `0.333333`
  Excerpt: Can I ask your honors to go to the next part of the Civil Liability Act?
  Candidate `fact:fae42de94d163cc8` score `0.333333`
  Excerpt: Can I ask your Honour to go to the next part of the Civil Liability Act .
  Candidate `fact:8fe28381242afe12` score `0.307692`
  Excerpt: [04:27:55.095 -> 04:28:12.775] That is, it's a civil liability of a person in respect of an intentional act so that it, it's it's not covered by part one of the Civil Liability Act, but is by part one B or is that, that's not part of your case one way or another.

## Provisional Structured Anchors

- `#1` `fact:fae42de94d163cc8#anchor:1` calendar_reference -> 2018 (score `68`)
- `#2` `fact:bbd1fda3545c8f7e#anchor:1` calendar_reference -> 2014 (score `62`)
- `#3` `fact:f642530dfd879730#anchor:1` calendar_reference -> 1965 (score `62`)
- `#4` `fact:70d7cdc9317e1dd1#anchor:1` transcript_timestamp_window -> 04:05:11.805 -> 04:05:28.755 (score `58`)
- `#5` `fact:8fe28381242afe12#anchor:1` transcript_timestamp_window -> 04:27:55.095 -> 04:28:12.775 (score `56`)

## Provisional Anchor Bundles

- `#1` `fact:fae42de94d163cc8` anchors `2` top-score `68`
- `#2` `fact:bbd1fda3545c8f7e` anchors `2` top-score `62`
- `#3` `fact:f642530dfd879730` anchors `2` top-score `62`
- `#4` `fact:70d7cdc9317e1dd1` anchors `1` top-score `58`
- `#5` `fact:8fe28381242afe12` anchors `1` top-score `56`
