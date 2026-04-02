# Wikidata Nat Cohort D Type-Probing Surface

Date: 2026-04-02

## Purpose

Turn Cohort D (subjects with no `instance of`) into a bounded type-probing
review artifact that remains fail-closed and non-executing.

This tranche extends the Cohort D review lane without changing cohort scope.

## Runtime Helper

- `SensibLaw/src/ontology/wikidata_nat_cohort_d_review.py`
- builder:
  `build_wikidata_nat_cohort_d_type_probing_surface(...)`

The builder projects:

- the Cohort D review surface fixture
- bounded reviewer packets for Cohort D probe rows

into one review-only type-probing artifact.

## Pinned Artifact

- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_d_type_probing_surface_20260402.json`

Current bounded output:

- artifact status: `review_only_ready`
- probe rows: `2` (`Q738421`, `Q1785637`)
- unresolved packet refs: `0`
- governance: `automation_allowed=false`, `can_execute_edits=false`,
  `promotion_guard=hold`, `fail_closed=true`

## Non-Claims

- no direct migration execution
- no checked-safe promotion from missing `instance of` alone
- no cross-cohort expansion (B/C/E remain out of scope)

## Next Gate

- keep gate as `type_probing_scan_review_only`
- if packet refs are missing, artifact status must remain
  `review_only_incomplete` and surface unresolved refs explicitly

