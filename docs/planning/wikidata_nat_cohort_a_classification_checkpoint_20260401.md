# Wikidata Nat Cohort A Classification Checkpoint

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Pin an explicit classification checkpoint for the first materialized Nat Cohort
A tranche so the lane advances from shape validation into bounded
migration-pack classification status.

This checkpoint does not claim broad migration readiness. It records the
current classified state for the revision-locked business-family tranche.

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_cohort_a_seed_slice_20260401.md`
- `SensibLaw/docs/planning/wikidata_nat_cohort_a_shape_scan_20260401.md`
- `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json`

## ZKP Frame

### O

Actors and surfaces:

- Nat lane operators and ontology working-group reviewers
- the historical Cohort A materialization fixture as bounded classified input
- migration-pack runtime as the classifier

### R

Required outcome:

- materialize the classifier result for the first Cohort A tranche as a
  first-class Nat artifact
- keep the lane fail-closed and explicit about current non-readiness

### C

Primary artifact surfaces:

- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_seed_slice_20260401.json`
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_classification_checkpoint_20260401.json`

### S

Measured classified tranche state:

- candidate count:
  `53`
- classification:
  `split_required = 53`
- action:
  `split = 53`
- requires review:
  `true = 53`
- checked-safe subset:
  none

### L

Nat-lane ordering now reaches:

1. proposal capture
2. cohort mapping
3. cohort manifests
4. Cohort A tranche materialization
5. Cohort A shape scan
6. Cohort A classification checkpoint
7. export gate
8. post-edit verification gate

### P

Proposal:

- freeze a bounded classification checkpoint for the current Cohort A tranche
- treat this as completion of the current classification milestone for the
  materialized bounded cohort scope
- keep broader cohort expansion as subsequent work

### G

Governance:

- classification checkpoint is review-state evidence, not execution authority
- all current rows remain review-first via `split_required`
- no checked-safe rows means no promotion path is implied here

### F

Gap closed by this slice:

- Nat now has an explicit per-cohort classification checkpoint artifact over
  the first materialized tranche

Remaining gap:

- no checked-safe rows exist in the current tranche
- post-edit verification remains open
- broader cohort coverage remains incomplete

## Checkpoint Summary

- entities:
  `Q10403939`, `Q10422059`
- candidate rows:
  `53`
- counts by classification:
  - `split_required`: `53`
- counts by action:
  - `split`: `53`
- requires review:
  - `true`: `53`
- checked-safe subset:
  empty

Common reasons:

- `mixed_temporal_resolution`
- `multi_value_slot`
- `multi_valued_dimension`
- `multiple_time_qualifiers`
- `time_range_requires_split`

Interpretation:

- the tranche is now not only materialized and shape-clean, but also explicitly
  classified
- it remains a decomposition-heavy review set rather than a migration-safe set

## Progress Update

Nat-lane completion now moves to:

- `6 / 8`
- `75%`

Completed milestones:

1. proposal page captured
2. task buckets mapped
3. review cohort manifests pinned
4. first bounded cohort migration-pack slice materialized
5. qualifier/reference shape scan completed
6. migration-pack classification checkpoint completed for the materialized
   bounded cohort

Remaining milestones:

7. checked-safe or review-only export artifacts produced
8. post-edit verification exercised

## ITIL Reading

- service:
  Nat-lane migration-review workflow
- change type:
  standard change
- risk:
  low, because this checkpoint records existing classifier output state only

## ISO 9000 Reading

- quality objective:
  ensure classification status is explicitly auditable, not inferred from
  upstream slices
- quality result:
  classification is now pinned as a dedicated Nat artifact

## Six Sigma Reading

Observed process variance:

- the tranche remains structurally decomposable and non-migrable as one-to-one
  rows

Control implication:

- keep split-heavy subsets review-first until explicit split-plan/export
  governance is satisfied

## C4 / PlantUML

```plantuml
@startuml
title Nat Cohort A Classification Checkpoint

Component(seed, "Cohort A Historical Slice", "First materialized candidate set")
Component(classifier, "MigrationPack Classifier", "Bounded classification surface")
Component(checkpoint, "Classification Checkpoint", "Pinned lane-state artifact")
Component(export_gate, "Export Gate", "Next readiness gate")

Rel(seed, classifier, "classified by")
Rel(classifier, checkpoint, "emits bounded status")
Rel(checkpoint, export_gate, "drives next gate")

@enduml
```
