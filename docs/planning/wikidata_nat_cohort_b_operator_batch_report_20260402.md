# Wikidata Nat Cohort B Operator Batch Evidence Surface

Date: 2026-04-02

## Scope

Lane-local Cohort B only:

- aggregates more than one Cohort B operator packet
- materializes deterministic queue + report evidence in one batch payload

No Cohort C/D/E behavior is changed.

## Runtime Helper

- `src/ontology/wikidata_nat_cohort_b_operator_batch_report.py`
- `build_nat_cohort_b_operator_batch_report(operator_packets, max_queue_items=100, max_examples=10)`

The batch helper composes:

1. `build_nat_cohort_b_operator_queue(...)`
2. `build_nat_cohort_b_operator_report(...)`

and emits:

- `case_summaries` and `packet_decision_counts`
- nested queue/report materialization
- `batch_status` with bounded fail-closed reasons

## Fail-Closed Rules

Batch status is `hold` when:

- fewer than two operator cases are provided
- queue is not ready
- report is not ready

This keeps the broader evidence lane review-only.

## Pinned Surface

- second-case packet fixture:
  `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_packet_case2_20260402.json`
- pinned batch fixture:
  `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_batch_report_20260402.json`
- regression tests:
  `tests/test_wikidata_nat_cohort_b_operator_batch_report.py`

## Non-Claims

- not migration execution
- not autonomous promotion
- not cross-cohort arbitration

