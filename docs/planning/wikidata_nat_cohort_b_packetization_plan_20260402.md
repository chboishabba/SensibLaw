# Wikidata Nat Cohort B Packetization Plan

Date: 2026-04-02

## Scope

Lane-local to **Cohort B only**:

- reconciled non-business `instance of` rows
- outside business-family tranche (`Q4830453`, `Q6881511`, `Q891723`)

This plan does not alter Cohort C/D/E handling.

## Runtime Surface (Bounded)

New helper surface:

- `src/ontology/wikidata_nat_cohort_b_review_bucket.py`
- `build_nat_cohort_b_review_bucket(payload)`

Bounded output:

- decision: `review_only` or `hold`
- `review_bucket_rows` with qualifier/reference variance flags
- reviewer questions per row
- contract violations for out-of-lane contamination

## Fail-Closed Contract

The helper holds (`decision=hold`) when:

- payload schema/version is wrong
- payload includes business-family rows
- payload includes unreconciled `instance of` rows
- no valid Cohort B rows remain after validation

No output path executes migrations.

## Packetization Slice

1. Materialize Cohort B candidate rows into `candidates`.
2. Build review bucket via `build_nat_cohort_b_review_bucket`.
3. If `decision=hold`, route to lane diagnostics only.
4. If `decision=review_only`, emit row-level reviewer prompts and variance
   flags for packet attachment or operator review.

## Expected Shape Baseline

Qualifier baseline:

- `P459`, `P3831`, `P585`, `P580`, `P582`, `P518`, `P7452`

Reference baseline:

- `P854`, `P1065`, `P813`, `P1476`, `P2960`

Variance outside these sets remains reviewer-visible; it is not silently
collapsed.

## Non-Claims

- not full semantic decomposition
- not migration execution authorization
- not cross-cohort generalization

