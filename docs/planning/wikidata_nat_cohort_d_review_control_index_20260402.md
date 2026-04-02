# Wikidata Nat Cohort D Review Control Index

Date: 2026-04-02

## Purpose

Add a broader Cohort D review-control surface that aggregates multiple Cohort D
batch reports while preserving explicit blockers and hold signals.

This is a deterministic index layer above batch reporting.

## Runtime Helper

- `SensibLaw/src/ontology/wikidata_nat_cohort_d_review.py`
- builder:
  `build_wikidata_nat_cohort_d_review_control_index(...)`

## CLI Surface

- `sensiblaw wikidata cohort-d-review-control-index --input <index_input.json> [--output <index.json>]`

## Pinned Artifacts

- input:
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_d_review_control_index_input_20260402.json`
- output:
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_d_review_control_index_20260402.json`

Current bounded output:

- index id: `cohort_d_review_control_index_20260402`
- batch count: `2`
- readiness:
  - `review_queue_ready`: `1`
  - `review_queue_incomplete`: `1`
- decision: `review`
- promotion allowed: `false`
- hold signals include incomplete batch and unresolved packet refs

## Governance

- fail-closed and non-executing
- no direct migration execution
- no checked-safe promotion from missing `instance of` alone

