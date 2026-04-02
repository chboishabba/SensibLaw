# Wikidata Nat Cohort B Operator Control Summary

Date: 2026-04-02

## Scope

Lane-local Cohort B repeated-run control surface:

- aggregates multiple Cohort B evidence indexes
- emits one deterministic control summary for broader-slice readiness tracking

No migration execution or cross-cohort routing is introduced.

## Runtime Surface

- helper:
  `src/ontology/wikidata_nat_cohort_b_operator_control_summary.py`
- builder:
  `build_nat_cohort_b_operator_control_summary(index_payloads, min_ready_indexes=2)`
- CLI:
  `cli/cohort_b_operator_control_summary.py`

The summary surfaces:

- per-index readiness entries
- ready/hold index counts and aggregate batch counts
- bounded control readiness status with explicit fail-closed reasons

## Fail-Closed Rules

Control status is `hold` when:

- validation errors exist
- ready index count is below threshold
- any hold index is present

Ready index ids are emitted only when `control_status=review_control_ready`.

## Pinned Surface

- evidence-index fixtures:
  - `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_evidence_index_20260402.json`
  - `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_evidence_index_case2_20260402.json`
- pinned control-summary fixture:
  `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_control_summary_20260402.json`
- tests:
  - `tests/test_wikidata_nat_cohort_b_operator_control_summary.py`
  - `tests/test_wikidata_nat_cohort_b_operator_control_summary_cli.py`

## Non-Claims

- not migration execution
- not autonomous promotion
- not cross-cohort arbitration

