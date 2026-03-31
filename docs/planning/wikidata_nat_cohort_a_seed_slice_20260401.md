# Wikidata Nat Cohort A Seed Slice

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Materialize the first bounded Nat-lane Cohort A slice from already pinned
revision-locked data so the lane advances from manifest-only planning into a
real migration-pack artifact.

This note keeps the original `seed` wording only as historical provenance for
the first bounded materialization step. Current Nat-lane operational language
should use `tranche` for live-discovered, repo-pinned classified subsets.

This slice is intentionally narrow:

- Cohort:
  reconciled business-family subjects
- entities:
  `Q10403939` (`Akademiska Hus`) and `Q10422059` (`Atrium Ljungberg`)
- source:
  existing revision-locked climate pilot pack already present in the repo

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_lane_cohort_manifests_20260401.md`
- `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/manifest.json`
- `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json`

## ZKP Frame

### O

Actors and surfaces:

- Nat lane cohort manifests as planning boundary
- pinned climate pilot pack as the revision-locked materialization source
- Cohort A seed slice as the first Nat-lane executable subset
- repo operators as reviewers of split-required pressure

### R

Required outcome:

- prove the Nat lane can materialize a real Cohort A migration-pack slice
- keep the slice bounded, revision-locked, and auditable
- avoid claiming that the whole business-family population is now materialized

### C

Primary artifact surfaces:

- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_lane_review_manifests_20260401.json`
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_seed_slice_20260401.json`
- `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json`

### S

Current materialized seed:

- `2` revision-locked business-family entities
- `53` candidate rows
- bucket distribution:
  - `split_required`: `53`
- checked-safe rows:
  - none

### L

Nat-lane ordering now reaches:

1. sandbox page
2. revision-locked source unit
3. cohort mapping note
4. pinned review manifests
5. first bounded Cohort A migration-pack seed slice
6. qualifier/reference shape scan
7. future export and verification

### P

Proposal:

- treat the existing climate pilot business-family subset as the first Nat
  Cohort A seed slice
- pin it as a Nat-specific artifact rather than duplicating the full pack
- use it to drive the now-pinned qualifier/reference expectation scan

### G

Governance:

- this seed slice is still review-first
- `split_required` remains the dominant current signal
- no execution claim follows from materialization alone

### F

Gap closed by this slice:

- the Nat lane now has its first real bounded cohort materialization

Remaining gap:

- qualifier/reference expectations are now compared for the seed, but not yet
  for the broader planned cohorts
- only a seed subset of Cohort A is materialized, not the full business-family
  population

## Historical Slice Definition

The first bounded historical slice is defined by:

- source cohort:
  `business_family_reconciled`
- instance-of anchor:
  `business (Q4830453)`
- entity set:
  - `Q10403939`
  - `Q10422059`
- migration-pack source:
  `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json`

## Historical Slice Summary

- candidate count:
  `53`
- classification counts:
  - `split_required`: `53`
- requires review:
  `53`
- checked-safe subset:
  empty

Interpretation:

- the first bounded business-family materialization is not blocked by capture
  or schema gaps
- it is blocked by actual multi-value / temporal / decomposition pressure
- that is a useful product-quality result because it proves the lane is
  fail-closed rather than silently flattening business-family emissions
  records into unsafe one-to-one rewrites

## Progress Update

Nat-lane completion now moves to:

- `4 / 8`
- `50%`

Completed milestones:

1. proposal page captured
2. task buckets mapped
3. review cohort manifests pinned
4. first bounded cohort migration-pack slice materialized

Remaining milestones:

5. DONE: qualifier/reference shape scan completed for the Cohort A seed
6. migration-pack classification completed across planned cohorts
7. checked-safe or review-only exports produced
8. post-edit verification exercised

## ITIL Reading

- service:
  Nat-lane migration-review workflow
- change type:
  standard change
- risk:
  low to medium, because this slice promotes an existing revision-locked pack
  into Nat-lane governance but still emits no edits

## ISO 9000 Reading

- quality objective:
  controlled progression from proposal capture to executable review artifacts
- quality result:
  the first business-family subset is now pinned as a reproducible audit point

## Six Sigma Reading

Observed defect mode:

- business-family records are highly decomposable and cannot be treated as
  trivial one-to-one rewrites

Control response:

- preserve the whole subset as `split_required` review pressure rather than
  compressing variance away

## C4 / PlantUML

```plantuml
@startuml
title Nat Cohort A Seed Slice

Component(manifests, "Nat Review Manifests", "Planning boundary")
Component(pilot, "Climate Pilot Migration Pack", "Revision-locked materialization source")
Component(seed, "Nat Cohort A Seed Slice", "Bounded business-family subset")
Component(review, "Review Queue", "Split-required operator handoff")

Rel(manifests, seed, "defines cohort")
Rel(pilot, seed, "provides revision-locked candidates")
Rel(seed, review, "emits split-required pressure")

@enduml
```
