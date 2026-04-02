# Wikidata Nat Cohort D Operator Report Batch Surface

Date: 2026-04-02

## Purpose

Broaden Cohort D operator review evidence from single-surface reporting to a
deterministic multi-case batch summary.

This remains non-executing and fail-closed.

## Runtime Helper

- `SensibLaw/src/ontology/wikidata_nat_cohort_d_review.py`
- builder:
  `build_wikidata_nat_cohort_d_operator_report_batch(...)`

## CLI Surface

- `sensiblaw wikidata cohort-d-operator-report-batch --input <batch_input.json> [--output <batch_report.json>]`

## Pinned Artifacts

- input:
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_d_operator_report_batch_input_20260402.json`
- output:
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_d_operator_report_batch_20260402.json`

Current bounded output:

- batch id: `cohort_d_operator_batch_20260402`
- case count: `2`
- readiness counts:
  - `review_queue_ready`: `1`
  - `review_queue_incomplete`: `1`
- decision: `review`
- promotion allowed: `false`

## Governance

- fail-closed batch summary only
- no direct migration execution
- no checked-safe promotion from missing `instance of` alone
- blocked signals are surfaced when any case is incomplete

