# Wikidata Nat Cohort C Branch State

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Pin the first bounded Nat Cohort C branch state for the non-GHG or missing
`determination method (P459)` lane.

This note does not claim live materialization, execution readiness, or any
checked-safe subset. It records the first governed branch seam so Cohort C
exists as explicit repo state instead of as an implied future option.

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_lane_cohort_manifests_20260401.md`
- `SensibLaw/docs/planning/wikidata_nat_cohort_a_live_tranche_20260401.md`
- `SensibLaw/docs/planning/wikidata_nat_cohort_a_review_only_export_20260401.md`
- `SensibLaw/docs/planning/wikidata_nat_cohort_a_classification_checkpoint_20260401.md`

## ZKP Frame

### O

Actors and surfaces:

- Nat lane operators
- ontology-working-group reviewers
- Cohort C policy-risk branch surface
- migration-pack runtime
- repo maintainers

### R

Required outcome:

- create a first bounded branch state for Cohort C
- keep the branch fail-closed and review-first
- make the branch discoverable through repo docs and fixtures

### C

Primary artifact surfaces:

- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_c_branch_20260401.json`
- `SensibLaw/docs/planning/wikidata_nat_lane_cohort_manifests_20260401.md`
- `TODO.md`

### S

Current repo-backed state:

- Cohort A is fully traced through live review-only export state
- the Nat lane has a clear branch decision to Cohort C in the working-group
  docs
- Cohort C itself did not yet exist as a pinned artifact before this slice

### L

Cohort C branch ordering now becomes:

1. Cohort A review-only state
2. branch decision to Cohort C
3. first Cohort C branch state pinned
4. future review-first population scan
5. future classification checkpoint
6. future export / verification, if ever warranted

### P

Proposal:

- pin a branch-state artifact that says Cohort C exists and is policy-risk
  first
- keep the branch empty of execution claims until a real population scan is
  performed

### G

Governance:

- no live-query authority is implied by the branch artifact
- no execution authority is implied by the branch artifact
- branch state is explicit repo memory, not a migration decision

### F

Gap closed by this note:

- Cohort C is now a first-class pinned branch state

Remaining gap:

- Cohort C still needs an actual population scan and classification work

## Branch State

The pinned Cohort C branch is:

- cohort id:
  `non_ghg_protocol_or_missing_p459`
- label:
  `Non-GHG protocol or missing P459`
- selection rule:
  statements where `determination method or standard (P459)` is missing or
  not GHG protocol
- risk level:
  `high`
- status:
  `branch_pinned`
- population:
  unknown
- next gate:
  `review_first_population_scan`

## Interpretation

- this is the smallest honest Cohort C artifact
- it preserves the policy-risk boundary without pretending the lane is ready
  for execution
- it is the correct next surface if the Nat work later needs a branch-first
  scan for the missing/non-GHG `P459` family

## ITIL Reading

- service:
  Nat lane migration-review workflow
- change type:
  standard change
- success measure:
  the policy-risk branch is visible and governed instead of implicit

## ISO 9000 Reading

- quality objective:
  make the branch-state boundary explicit before any population work starts
- quality result:
  Cohort C now exists as a controlled branch artifact

## Six Sigma Reading

Observed defect mode:

- branch drift from implied future work

Control response:

- pin the branch state before any live scan or classification work

## C4 / PlantUML

```plantuml
@startuml
title Nat Cohort C Branch State

Component(a, "Cohort A Review-Only State", "Current bounded tranche")
Component(c, "Cohort C Branch State", "Non-GHG / missing P459 branch")
Component(scan, "Future Population Scan", "Review-first discovery")
Component(review, "Ontology Working Group", "Policy review surface")

Rel(a, c, "branch to")
Rel(c, scan, "next gate")
Rel(scan, review, "feeds")

@enduml
```
