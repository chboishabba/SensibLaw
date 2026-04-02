# Wikidata Nat Cohort D Operator/Reviewer Surface

Date: 2026-04-02

## Purpose

Package the Cohort D type-probing artifact into an operator/reviewer queue
surface while staying fail-closed and non-executing.

This is a bounded packaging layer above the existing type-probing helper.

## Runtime Helper

- `SensibLaw/src/ontology/wikidata_nat_cohort_d_review.py`
- builder:
  `build_wikidata_nat_cohort_d_operator_review_surface(...)`

## Pinned Artifact

- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_d_operator_review_surface_20260402.json`

Current bounded output:

- readiness: `review_queue_ready`
- queue size: `2`
- unresolved packet refs: `0`
- execution: disallowed for every queue row

## Queue Semantics

- each queue row includes:
  - review entity qid
  - packet id
  - split plan id
  - smallest next check
  - recommended next step
  - uncertainty flags
  - priority
- governance remains explicit:
  - `automation_allowed=false`
  - `can_execute_edits=false`
  - `promotion_guard=hold`
  - `fail_closed=true`

## Non-Claims

- no direct migration execution
- no checked-safe promotion from missing `instance of` alone
- no cohort widening beyond Cohort D

