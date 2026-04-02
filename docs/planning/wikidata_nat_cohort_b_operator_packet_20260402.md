# Wikidata Nat Cohort B Operator Packet (Bounded)

Date: 2026-04-02

## Scope

Lane-local Cohort B tranche only:

- reconciled non-business `instance of` rows
- review-first packet surface for operators/reviewers

No Cohort C/D/E routing is changed by this slice.

## Runtime Helper

- `src/ontology/wikidata_nat_cohort_b_operator_packet.py`
- `build_nat_cohort_b_operator_packet(review_bucket_payload, max_rows=5)`

Pinned fixture contract:

- input fixture:
  `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_packet_input_20260402.json`
- expected packet fixture:
  `tests/fixtures/wikidata/wikidata_nat_cohort_b_operator_packet_20260402.json`
- regression test:
  `tests/test_wikidata_nat_cohort_b_operator_packet.py`

Input contract:

- payload from `build_nat_cohort_b_review_bucket(...)`
- cohort id must be `cohort_b_reconciled_non_business`
- source bucket decision must be `review_only` or `hold`

Output contract:

- packet decision: `review` or `hold`
- selected rows (bounded by `max_rows`)
- variance-flag counts for reviewer triage
- fail-closed governance fields and non-claims

## Fail-Closed Rules

The operator packet holds when:

- source bucket is `hold`
- no valid review rows are available
- input shape is invalid

The helper never authorizes migration execution.

## Reviewer Surface

- triage prompts prioritize:
  - unexpected qualifier variance
  - unexpected reference variance
  - temporal qualifier-mode mixing
- rows are ordered by variance pressure first
- contract violations stay visible for operator correction

## Non-Claims

- not a migration executor
- not full semantic decomposition
- not cross-cohort arbitration
