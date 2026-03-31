# Wikidata Ontology Group Handoff: Nat Lane

Date: 2026-04-01

## Purpose

Provide one short ontology-group handoff for the Nat WDU
`P5991 -> P14143` migration lane after the recent normalization work.

This is the working-group-facing summary of:

- what is now pinned
- what is still blocked
- what the next decision actually is

## Executive State

The Nat lane is now normalized enough to be discussed as a governed migration
review workflow rather than as a loose sandbox proposal.

Current bounded progress:

- `7 / 8`
- `87.5%`

Completed:

1. Nat sandbox page captured as revision-locked `wiki_revision` source unit
2. task buckets mapped into five normalized cohorts
3. explicit cohort manifests pinned
4. first bounded Cohort A tranche materialized
5. Cohort A qualifier/reference shape scan completed
6. Cohort A classification checkpoint completed for the materialized seed
7. review-only export artifacts produced

Remaining:

8. post-edit verification on any promoted subset

## What Is Pinned Now

Proposal capture and mapping:

- `docs/planning/wikidata_nat_wdu_sandbox_migration_mapping_20260401.md`
- `tests/fixtures/wikidata/wiki_revision_nat_wdu_sandbox_p5991_p14143_20260401.json`

Nat-lane cohort model:

- `docs/planning/wikidata_nat_lane_cohort_manifests_20260401.md`
- `tests/fixtures/wikidata/wikidata_nat_lane_review_manifests_20260401.json`

First bounded business-family materialization:

- `docs/planning/wikidata_nat_cohort_a_seed_slice_20260401.md`
- `tests/fixtures/wikidata/wikidata_nat_cohort_a_seed_slice_20260401.json`

First shape verification:

- `docs/planning/wikidata_nat_cohort_a_shape_scan_20260401.md`
- `tests/fixtures/wikidata/wikidata_nat_cohort_a_shape_scan_20260401.json`

First classification checkpoint:

- `docs/planning/wikidata_nat_cohort_a_classification_checkpoint_20260401.md`
- `tests/fixtures/wikidata/wikidata_nat_cohort_a_classification_checkpoint_20260401.json`

First live Cohort A expansion:

- `docs/planning/wikidata_nat_cohort_a_live_tranche_20260401.md`
- `tests/fixtures/wikidata/wikidata_nat_cohort_a_live_discovery_20260401.json`
- `tests/fixtures/wikidata/wikidata_nat_cohort_a_live_tranche_20260401.json`

## Working-Group Meaning

The main product-quality result so far is not that the lane found a large safe
rewrite subset.

It is that the lane is now fail-closed in a normalized way:

- revision-locked wiki proposal admitted cleanly
- cohorts made explicit
- business-family tranche materialized from pinned data
- expected qualifier/reference shape checked explicitly
- current business-family tranche remains `split_required` rather than being
  flattened into false one-to-one migrations

That is the correct ontology-group posture for this stage.

## Current Cohort A Result

Bounded tranche:

- entities:
  `Q10403939` (`Akademiska Hus`)
  `Q10422059` (`Atrium Ljungberg`)
- candidate rows:
  `53`
- classification:
  - `split_required`: `53`
- checked-safe subset:
  none

Measured shape:

- actual qualifiers:
  `P3831`, `P459`, `P518`, `P580`, `P582`
- actual references:
  `P854`
- unexpected qualifier/reference properties:
  none

Interpretation:

- shape is clean relative to the Nat expectation set
- semantics are still decompositional and review-first
- the first live tranche confirms the same posture at larger size:
  - `4` QIDs
  - `188` candidate rows
  - checked-safe subset:
    none

## Decision Needed From The Group

The next bounded branch is now clear:

Option A:
run a targeted checked-safe hunt inside Cohort A

Option B:
branch to Cohort C, the higher-risk lane where `P459` is missing or not GHG
protocol

Recommended next move:

- stop blind business-family expansion and switch to a targeted checked-safe
  search inside Cohort A
- only branch to Cohort C once the group wants to confront policy-risk rather
  than shape/structure risk

Reason:

- Cohort A is already pinned, materialized, shape-checked, and now also
  live-expanded without surfacing a safe subset
- Cohort C is more governance-heavy and is likely to produce more policy-hold
  outcomes than structural learning at this moment

## Governance Reminder

The sandbox page is now useful group input, but it is still not the direct
executor.

The runtime remains responsible for:

- per-statement classification
- split detection
- checked-safe gating
- export eligibility
- post-edit verification

## Suggested Group Handoff Wording

The Nat `P5991 -> P14143` lane is no longer just a sandbox discussion.
It is now a bounded review workflow with explicit cohorts, a materialized
business-family tranche, and a clean shape check. The current result is not “safe
rewrite,” but “structured split-required pressure.” The next group decision is
whether to run a targeted checked-safe hunt inside Cohort A or pivot into the higher-risk
non-GHG / missing-`P459` lane.
