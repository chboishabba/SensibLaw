# Wikidata Nat Cohort A Review-Only Export

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Satisfy the Nat export gate honestly for the current Cohort A tranche by emitting
review-only export artifacts instead of pretending a checked-safe subset
exists.

This slice is bounded to the already-materialized and already-classified
business-family tranche.

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_cohort_a_classification_checkpoint_20260401.md`
- `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json`
- `SensibLaw/docs/planning/wikidata_split_plan_contract_20260328.md`

## ZKP Frame

### O

- Nat lane operators
- ontology working-group reviewers
- migration-pack export surface
- split-plan review surface

### R

- produce a bounded review-only export artifact for the current Cohort A tranche
- keep the lane fail-closed because there is still no checked-safe subset

### C

- planned artifacts:
  - `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_review_only_export_20260401.csv`
  - `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_review_only_export_20260401.json`
  - `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_split_plan_20260401.json`

### S

- the current tranche has:
  - `53` rows
  - `split_required = 53`
  - no checked-safe rows
- that means the correct export gate is review-only, not checked-safe

### L

1. proposal capture
2. cohort mapping
3. cohort manifests
4. seed materialization
5. shape scan
6. classification checkpoint
7. review-only export artifacts
8. post-edit verification on any promoted subset

### P

- export the current tranche as a review CSV for operator-facing work
- also pin the corresponding split plan because the seed is entirely
  `split_required`
- treat that pair as completion of the current export milestone

### G

- no checked-safe export claim
- no direct edit payloads
- no post-edit verification claim yet

### F

- the remaining final gap after this slice will be post-edit verification on
  any future promoted subset

## Export Contract For This Slice

The current Cohort A export gate is satisfied only if:

- the review CSV exists and reflects all `53` current seed rows
- the review CSV remains review-first
- the split plan exists and remains review-only

## Progress Update

Nat-lane completion now moves to:

- `7 / 8`
- `87.5%`

Completed milestones:

1. proposal page captured
2. task buckets mapped
3. review cohort manifests pinned
4. first bounded cohort migration-pack slice materialized
5. qualifier/reference shape scan completed
6. classification checkpoint completed
7. review-only export artifacts produced

Remaining milestone:

8. post-edit verification exercised on any promoted subset

## ITIL Reading

- service:
  Nat migration-review workflow
- change type:
  standard change
- success condition:
  export gate is satisfied without weakening the fail-closed posture

## ISO 9000 Reading

- quality objective:
  export only what the lane is actually ready to export
- quality result:
  review-only output is now first-class rather than implicit

## Six Sigma Reading

Observed defect risk:

- treating the absence of checked-safe rows as a reason to skip explicit export
  state

Control response:

- emit the review-only export surface directly

## C4 / PlantUML

```plantuml
@startuml
title Nat Cohort A Review-Only Export

Component(checkpoint, "Classification Checkpoint", "Bounded classified state")
Component(csv, "Review CSV", "Operator-facing export")
Component(split, "Split Plan", "Review-only decomposition artifact")
Component(verify, "Post-Edit Verification", "Remaining final gate")

Rel(checkpoint, csv, "exports review rows")
Rel(checkpoint, split, "exports split review plan")
Rel(csv, verify, "precedes")
Rel(split, verify, "precedes")

@enduml
```
