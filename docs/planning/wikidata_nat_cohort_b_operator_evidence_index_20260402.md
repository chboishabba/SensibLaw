# Wikidata Nat Cohort B Operator Evidence Index

Date: 2026-04-02

## Scope

Lane-local Cohort B broader operator control surface:

- aggregates multiple Cohort B batch reports
- emits one deterministic evidence index for broader-slice review readiness

No shared cross-cohort routing or execution semantics are introduced.

## Runtime Surface

- helper:
  `src/ontology/wikidata_nat_cohort_b_operator_evidence_index.py`
- builder:
  `build_nat_cohort_b_operator_evidence_index(batch_reports, min_ready_batches=2)`
- CLI materializer:
  `cli/cohort_b_operator_index.py`

The index summarizes:

- per-batch readiness entries
- ready/hold counts and reasons
- ready-batch ids only when threshold is met
- fail-closed validation diagnostics

## Fail-Closed Rules

Index status is `hold` when:

- validation errors are present
- ready-batch count is below threshold

Ready-batch ids are suppressed in hold status.

## Pinned Surface

- batch fixtures:
  - `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_batch_report_20260402.json`
  - `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_batch_report_case2_20260402.json`
- pinned index fixture:
  `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_evidence_index_20260402.json`
- tests:
  - `tests/test_wikidata_nat_cohort_b_operator_evidence_index.py`
  - `tests/test_wikidata_nat_cohort_b_operator_index_cli.py`

## Non-Claims

- not migration execution
- not autonomous promotion
- not cross-cohort arbitration

