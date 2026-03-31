# Wikidata Nat Cohort A Checked-Safe Hunt

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Run one bounded checked-safe hunt inside Nat Cohort A after the first live
tranche returned only `split_required` rows.

This slice keeps the same governance boundary:

- live discovery is candidate search only
- pinned tranche artifacts remain the governed truth surface
- no direct edit execution follows from classification alone

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_cohort_a_live_tranche_20260401.md`
- `SensibLaw/docs/planning/wikidata_nat_lane_cohort_manifests_20260401.md`
- live WDQS query constrained to:
  - `P5991`
  - `P31 in {Q4830453, Q6881511, Q891723}`
  - `qualifierCount <= 2`
- materializer:
  - `SensibLaw/scripts/materialize_wikidata_migration_pack.py`

## ZKP Frame

### O

- Nat operators and ontology-group reviewers
- live WDQS probe for bounded candidate identification
- migration-pack materializer and pinned tranche fixture surfaces

### R

- find the next bounded Cohort A tranche with the highest chance of yielding a
  checked-safe subset
- keep the hunt deterministic, small, and fail-closed

### C

- this planning note
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_checked_safe_hunt_20260401.json`
- `/tmp/wikidata_nat_cohort_a_checked_safe_hunt_20260401` (local runtime
  output only)

### S

Targeted low-complexity probe returned:

- `Q1068745` (`Check24`)
- `Q1489170` (`immowelt`)

Materialized bounded tranche result:

- candidate rows:
  `2`
- checked-safe subset count:
  `2`
- requires review count:
  `0`
- classification:
  - `safe_with_reference_transfer`: `2`

### L

1. first live tranche (split-only)
2. targeted checked-safe hunt
3. checked-safe subset found and pinned
4. next gate: post-edit verification on a promoted bounded subset

### P

- pin this low-complexity two-QID tranche as the first Nat Cohort A
  checked-safe hunt artifact
- treat it as readiness input for the final Nat verification gate

### G

- checked-safe classification is still not execution completion
- Nat remains incomplete until post-edit verification is exercised
- no broad completion claim from this slice

### F

Gap closed:

- Nat now has a pinned checked-safe candidate subset in Cohort A instead of
  only split-only evidence

Remaining gap:

- post-edit verification is still required for completion

## Discovery And Tranche Result

Bounded probe criteria:

- business-family `instance of`
- low qualifier complexity (`<= 2` qualifier families)
- minimal statement count preference

Selected QIDs:

- `Q1068745` (`Check24`)
- `Q1489170` (`immowelt`)

Tranche summary:

- candidate ids:
  - `Q1068745|P5991|1`
  - `Q1489170|P5991|1`
- checked-safe subset:
  - `Q1068745|P5991|1`
  - `Q1489170|P5991|1`
- action:
  - `migrate_with_refs` for both

Interpretation:

- the targeted hunt succeeded
- the lane now has a bounded checked-safe subset to carry into verification

## Progress

Nat progress remains:

- `7 / 8`
- `87.5%`

Reason:

- this slice finds and pins a checked-safe subset, but the remaining gate is
  still post-edit verification

## ITIL Reading

- service:
  Nat migration-review workflow
- change type:
  standard change
- outcome:
  bounded checked-safe hunt completed and pinned

## ISO 9000 Reading

- quality objective:
  replace broad search with controlled, reproducible checked-safe hunting
- quality result:
  two-row checked-safe tranche with explicit provenance and revision basis

## Six Sigma Reading

Observed variance:

- high-complexity tranches were uniformly split-required

Control response:

- low-complexity bounded probe to increase checked-safe yield probability

## C4 / PlantUML

```plantuml
@startuml
title Nat Cohort A Checked-Safe Hunt

Component(probe, "Low-Complexity WDQS Probe", "Bounded candidate search")
Component(materializer, "Migration Pack Materializer", "Revision-locked tranche build")
Component(tranche, "Checked-Safe Hunt Fixture", "Pinned governed artifact")
Component(verify, "Post-Edit Verification Gate", "Final Nat completion gate")

Rel(probe, materializer, "provides QIDs")
Rel(materializer, tranche, "materializes and pins")
Rel(tranche, verify, "feeds promoted subset candidate")

@enduml
```
