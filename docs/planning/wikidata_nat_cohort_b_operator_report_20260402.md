# Wikidata Nat Cohort B Operator Report Surface

Date: 2026-04-02

## Scope

Lane-local Cohort B review-only reporting surface:

- consumes Cohort B operator queue payloads
- emits bounded reviewer-facing operator reports

No cross-cohort routing or execution semantics are introduced.

## Runtime Helper

- `src/ontology/wikidata_nat_cohort_b_operator_report.py`
- `build_nat_cohort_b_operator_report(queue_payload, max_examples=5)`

Output shape includes:

- `report_status` (`review_only_report_ready` or `hold`)
- queue-derived examples for bounded operator briefing
- summary counts by priority, variance flags, and `instance of` classes
- blocked packet + validation diagnostics

## Fail-Closed Rules

- if queue status is not `review_queue_ready`, report status is `hold`
- when `hold`, examples are empty and diagnostics stay visible
- report remains non-executing and review-first

## Pinned Surface

- input queue fixture:
  `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_queue_20260402.json`
- pinned report fixture:
  `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_report_20260402.json`
- regression test:
  `tests/test_wikidata_nat_cohort_b_operator_report.py`

## Non-Claims

- not migration execution
- not autonomous approval
- not cross-cohort arbitration

