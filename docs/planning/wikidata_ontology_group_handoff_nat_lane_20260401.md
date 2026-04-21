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

- bounded mainline: complete
- wider proof lane: complete
- wider online lane: held
- split-plan-first continuation: active

Completed:

1. Nat sandbox page captured as revision-locked `wiki_revision` source unit
2. task buckets mapped into normalized cohorts
3. explicit cohort manifests pinned
4. checked-safe subset found and post-edit verified on bounded rows
5. wider proof lane completed
6. wider online passes executed honestly and then held after repeated
   zero-yield direct-safe tranches
7. split-plan-first review surface built for wider held rows
8. split verification now exists in both single-plan and batch form

Current missing layer:

- generic reviewer packets for split-heavy rows using bounded wiki parsing and
  selected followed-source receipts

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

Split-verification branch:

- `docs/planning/wikidata_split_verification_contract_20260401.md`
- `docs/planning/wikidata_nat_split_verification_pilot_q30938280_20260401.md`
- `docs/planning/wikidata_nat_split_verification_pilot_q3356220_20260401.md`
- `tests/fixtures/wikidata/wikidata_nat_split_verification_multi_plan_surface_20260401.json`

End-product and next-layer planning:

- `docs/planning/wikidata_nat_end_product_and_tiered_automation_20260401.md`
- `docs/planning/wikidata_review_packet_plan_20260401.md`

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

## April 21 Routing Clarification

The Nat source cohorts and the April 12 routing families should be kept
separate:

- Nat cohorts describe where the row came from in the sandbox population.
- Routing families describe what action is justified after inspection.

Current routing table:

- Family A: clean model-aligned rows route to `full_auto`.
- Family B: structured rows with multiple scopes, totals, or years route to
  `split_auto`.
- Family C: model-incomplete rows, including missing `P459`, route to repair
  plus migrate review.
- Family D: valid but weakly typed or semantically mismatched subjects route to
  review-only typed hold.
- Family E: broken or legacy mixed rows route to manual reconstruction.

Conservative property boundary:

- annual organization-level emissions route to `P14143`
- product or lifecycle carbon footprint stays on `P5991`
- emissions intensity, avoided emissions, offsets, and removals stay held
  unless a specific target property is confirmed
- non-emissions metrics are blocked

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

The next bounded branch is now different from the earlier checkpoint.

The direct-safe search has already done its job. The wider online lane showed
that broader Cohort A passes are predominantly split/review work, not direct
rewrite work.

Recommended next move:

- stop widening blind online passes
- build the generic reviewer-packet layer for split-heavy rows
- keep Cohort C as a distinct policy-risk branch rather than mixing it into the
  mainline

Reason:

- the lane already proved direct-safe handling on a bounded subset
- the lane already proved wider Cohort A is mostly split-required
- the highest-value next improvement is reviewer throughput and reduced
  uncertainty, not another proof that the same rows are hard

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
It now has a complete bounded mainline, a completed wider proof lane, and a
held wider online lane that honestly shows the broader business-family surface
is mostly review-and-split rather than direct-safe rewrite. The next useful
product step is not more blind widening. It is a reviewer-packet layer that
parses bounded wiki surfaces, exposes cited references and selected followed
sources, and helps reviewers process split-heavy rows faster without turning
page text into authority.
