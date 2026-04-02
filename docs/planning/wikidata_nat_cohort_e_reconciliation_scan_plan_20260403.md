# Cohort E Reconciliation Scan Plan

Date: 2026-04-03

## Purpose

Turn Cohort E from framing into a bounded review-first helper lane by
pinning the diagnostics surface reviewers need when typing remains
unreconciled.

## Scope

- this note stays inside Cohort E: `unreconciled instance of`
- it documents the diagnostics helper, not any shared roadmaps or
  execution lanes
- the lane remains `review_only`

## Plan

1. capture the `split://` plans for the 142 Cohort E statements
2. normalize their merged split axes so we have a canonical axis map per row
3. compare each row’s axes to the axes already solved by other cohorts
4. record agreement/disagreement per axis plus the suggested action
5. emit a bounded report that reviewers can inspect before any reconciliation
   (the `wikidata_nat_cohort_e_split_axis_sample_20260403.json` fixture captures
   two canonical axis maps as a reference)

## Fail-Closed Posture

- only emit the diagnostics; every row stays in Cohort E until a reconciliation
  path is documented
- no row is promoted or migrated without human confirmation of resolved typing

## Sample Fixture

- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_e_split_axis_sample_20260403.json`
  (a tiny subset of candidate axis maps) can seed the helper and keep
  reviewers aligned.
- pinned diagnostics report fixture:
  `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_e_diagnostic_report_20260403.json`
  shows how the helper reports hold-first disagreement results.
