# Wikidata Nat Lane Cohort Manifests

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Turn the Nat WDU sandbox migration mapping into explicit bounded review cohort
artifacts so the lane can progress from proposal capture to auditable
migration-pack execution planning.

This note does not widen migration authority. It defines the minimal
manifest-layer needed for the repo to:

- preserve the sandbox page's cohort buckets as explicit artifacts
- preserve expected qualifier/reference shape as cohort constraints
- report progress against a finite completion model for the Nat lane

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_wdu_sandbox_migration_mapping_20260401.md`
- `SensibLaw/docs/planning/wikidata_migration_pack_contract_20260328.md`
- `SensibLaw/docs/planning/wiki_revision_source_unit_lattice_admission_20260401.md`
- `SensibLaw/tests/fixtures/wikidata/wiki_revision_nat_wdu_sandbox_p5991_p14143_20260401.json`

## ZKP Frame

### O

Actors and surfaces:

- Nat (WDU) sandbox page as upstream proposal/cohort surface
- SensibLaw planning notes as normalization layer
- review cohort manifests as bounded operator-facing artifacts
- migration-pack runtime as the future cohort executor
- repo operators as promotion and verification decision makers

### R

Required outcome:

- represent the Nat task buckets as explicit bounded cohort artifacts
- attach the expected qualifier/reference families to those cohorts
- expose a measurable lane-completion model instead of leaving progress
  implicit

### C

Primary artifact surfaces:

- `SensibLaw/docs/planning/wikidata_nat_wdu_sandbox_migration_mapping_20260401.md`
- `SensibLaw/tests/fixtures/wikidata/wiki_revision_nat_wdu_sandbox_p5991_p14143_20260401.json`
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_lane_review_manifests_20260401.json`

### S

Current state before this slice:

- the Nat page is already captured as a revision-locked `wiki_revision`
  source-unit fixture
- the page is already mapped into five cohort families narratively
- the repo does not yet pin those cohorts as explicit review artifacts
- the repo does not yet report current progress versus total for the Nat lane

### L

Normalized ordering for the Nat lane now becomes:

1. sandbox page
2. revision-locked source unit
3. cohort mapping note
4. pinned review cohort manifests
5. materialized migration-pack cohorts
6. checked-safe / review-only / split-required / held outputs
7. post-edit verification for any promoted subset

### P

Proposal:

- create one bounded review-manifest fixture containing the five cohort
  families
- keep the fixture proposal-only and non-executing
- define a finite completion model so progress can be reported consistently

### G

Governance:

- the manifests define review scope and expected-shape constraints
- they do not fetch live data
- they do not emit edits
- migration-pack runtime remains the per-statement classification surface

### F

Gap closed by this slice:

- the Nat lane now has explicit cohort artifacts instead of narrative-only
  planning
- the Nat lane now has a measurable progress model

Remaining gap after this slice:

- the full cohort families are not yet materialized from live query results
  into real migration packs
- the qualifier/reference expectations are checked for the first Cohort A
  tranche, but not yet against the full planned cohort family
- the current classification checkpoint is completed for the materialized
  bounded cohort, not the full planned cohort family
- a targeted checked-safe hunt now exists in Cohort A, but the final post-edit
  verification gate remains open

## Cohort Manifest Contract

The bounded Nat review-manifest fixture should carry:

- `lane_id`
- `source_revision_fixture`
- `source_property`
- `target_property`
- `expected_qualifier_properties`
- `expected_reference_properties`
- `cohorts`
- `completion_model`
- `summary`

Each cohort should carry:

- `cohort_id`
- `label`
- `status`
- `population`
- `selection_rule`
- `risk_level`
- `expected_qualifier_properties`
- `expected_reference_properties`
- `next_gate`

This is intentionally a planning-layer artifact, not a runtime schema claim.

## Pinned Cohorts

The initial five cohorts are:

1. `business_family_reconciled`
2. `other_reconciled_instance_of`
3. `non_ghg_protocol_or_missing_p459`
4. `missing_instance_of`
5. `unreconciled_instance_of`

Population counts pinned from the sandbox snapshot:

- `business_family_reconciled`: `37665`
- `other_reconciled_instance_of`: unknown
- `non_ghg_protocol_or_missing_p459`: unknown
- `missing_instance_of`: `1395`
- `unreconciled_instance_of`: `142`

## Completion Model

The Nat lane is measured against eight bounded milestones:

1. proposal page captured as revision-locked source unit
2. migration task buckets mapped into normalized cohorts
3. explicit review cohort manifests pinned
4. first bounded cohort migration-pack slice materialized
5. expected qualifier/reference shape scanned against cohort data
6. per-cohort migration-pack classification completed
7. checked-safe or review-only export artifacts produced
8. post-edit verification exercised on any promoted subset

Current repo state after this slice:

- completed: `1` through `7`
- remaining: `8`

Normalized progress:

- `7 / 8`
- `87.5%`

## Roadmap To Complete Nat Lane

### Phase 1: materialize cohorts

- DONE: materialize Cohort A as the first bounded migration-pack tranche
  using the revision-locked business-family subset already present in:
  `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/`
- preserve separate manifests for Cohorts B through E
- keep unknown-population cohorts explicit rather than collapsing them

### Phase 2: shape verification

- DONE: scan qualifier families across the first materialized Cohort A tranche
- DONE: scan reference families across the first materialized Cohort A tranche
- surface unexpected qualifier/reference properties as review pressure

### Phase 3: per-cohort classification

- DONE: pin a migration-pack classification checkpoint for the first
  materialized Cohort A tranche
- build migration packs for each remaining planned cohort
- separate checked-safe rows from split-required, held, and review-only rows
- keep Cohorts C, D, and E review-first by default

### Phase 4: export and verify

- DONE: emit review-only export artifacts for the current classified Cohort A
  tranche
- DONE: run a bounded targeted checked-safe hunt in Cohort A and pin the
  resulting checked-safe tranche artifact
- export only the checked-safe subset from eligible cohorts
- run post-edit verification on the promoted subset
- leave any remaining unresolved cohorts as explicit review artifacts

## ITIL Reading

- service:
  Nat lane migration-review workflow
- change class:
  standard change
- risk:
  low, because this slice adds planning and pinned artifacts only
- success measure:
  Nat lane progress can now be reported against finite milestones rather than
  narrative status only

## ISO 9000 Reading

- quality objective:
  reproducible cohort-level migration review with preserved provenance and
  explicit completion gates
- quality improvement in this slice:
  progress reporting becomes standardized and comparable across future turns

## Six Sigma Reading

Primary defect classes addressed here:

- hidden cohort drift
- narrative-only progress reporting
- qualifier/reference expectation loss between proposal and execution

Control mechanism:

- one pinned manifest artifact preserves the cohort partition and expected
  shape constraints in one place

## C4 / PlantUML

```plantuml
@startuml
title Nat Lane Cohort Manifests

Component(page, "Nat WDU Sandbox Page", "Proposal / cohort source")
Component(sourceunit, "wiki_revision SourceUnit", "Revision-locked capture")
Component(mapping, "Mapping Note", "Cohort interpretation")
Component(manifests, "Review Cohort Manifests", "Pinned bounded artifacts")
Component(pack, "MigrationPack Runtime", "Per-cohort classifier")
Component(review, "Review / Verification", "Promotion gate")

Rel(page, sourceunit, "captured as")
Rel(sourceunit, mapping, "interpreted by")
Rel(mapping, manifests, "pins cohort partitions and constraints")
Rel(manifests, pack, "drives bounded cohort materialization")
Rel(pack, review, "emits checked-safe / review-only / split-required")

@enduml
```
