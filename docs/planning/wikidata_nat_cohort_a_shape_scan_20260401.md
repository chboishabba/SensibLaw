# Wikidata Nat Cohort A Shape Scan

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Measure the first materialized Nat Cohort A tranche against the expected
qualifier and reference families inherited from the Nat WDU sandbox page.

This slice answers one concrete question:

- does the first revision-locked business-family tranche leak any qualifier or
  reference properties outside the expected Nat shape?

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_lane_cohort_manifests_20260401.md`
- `SensibLaw/docs/planning/wikidata_nat_cohort_a_seed_slice_20260401.md`
- `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json`

## ZKP Frame

### O

Actors and surfaces:

- Nat review manifests as expected-shape authority
- the first Cohort A tranche as the measured population
- shape-scan artifact as the comparison record

### R

Required outcome:

- compare actual Cohort A tranche qualifier/reference properties against the Nat
  expected shape
- surface any unexpected properties explicitly
- update Nat-lane progress only if the comparison is pinned as an artifact

### C

Primary artifact surfaces:

- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_seed_slice_20260401.json`
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_shape_scan_20260401.json`

### S

Measured tranche:

- entities:
  `Q10403939`, `Q10422059`
- candidate rows:
  `53`

Measured actual property sets:

- qualifiers:
  `P3831`, `P459`, `P518`, `P580`, `P582`
- references:
  `P854`

Unexpected properties found:

- qualifiers:
  none
- references:
  none

### L

Nat-lane ordering now reaches:

1. sandbox page
2. revision-locked source unit
3. cohort mapping note
4. review manifests
5. Cohort A tranche materialization
6. Cohort A shape scan
7. future broader cohort classification
8. future export and verification

### P

Proposal:

- accept Cohort A tranche shape as consistent with the Nat sandbox expectation
- keep the result bounded to the first materialized tranche
- defer any wider generalization until more of Cohort A or Cohort B is
  materialized

### G

Governance:

- shape cleanliness does not imply migration safety
- `split_required` remains the dominant classification signal
- shape scan is a necessary but not sufficient gate

### F

Gap closed by this slice:

- the Nat lane now has an explicit qualifier/reference expectation check over
  a real materialized cohort subset

Remaining gap:

- broader cohort classification still stops at the tranche subset
- no export or post-edit verification has occurred

## Scan Result

Expected qualifier family from Nat manifests:

- `P459`
- `P3831`
- `P585`
- `P580`
- `P582`
- `P518`
- `P7452`

Actual qualifier family in the tranche:

- `P3831`
- `P459`
- `P518`
- `P580`
- `P582`

Expected reference family from Nat manifests:

- `P854`
- `P1065`
- `P813`
- `P1476`
- `P2960`

Actual reference family in the tranche:

- `P854`

Interpretation:

- the tranche is a strict subset of the expected Nat shape
- the shape scan found no unexpected qualifier families
- the shape scan found no unexpected reference families
- missing expected properties are not defects here; they simply did not occur
  in this bounded tranche

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

Remaining milestones:

7. checked-safe or review-only exports produced
8. post-edit verification exercised

## ITIL Reading

- service:
  Nat-lane migration-review workflow
- change type:
  standard change
- risk:
  low, because the scan only records measured cohort structure

## ISO 9000 Reading

- quality objective:
  prove that expected-shape constraints are actually checked against materialized
  data rather than assumed
- quality result:
  Cohort A tranche is shape-clean relative to the Nat expectation set

## Six Sigma Reading

Observed variance result:

- no unexpected qualifier/reference families were detected in the tranche

Control implication:

- the next variability concern is semantic decomposition, not shape leakage

## C4 / PlantUML

```plantuml
@startuml
title Nat Cohort A Shape Scan

Component(manifest, "Nat Review Manifests", "Expected shape source")
Component(seed, "Cohort A Historical Slice", "Measured candidate set")
Component(scan, "Shape Scan", "Expected vs actual property comparison")
Component(review, "Next Cohort Gate", "Broader classification / export decision")

Rel(manifest, scan, "provides expected qualifier/reference sets")
Rel(seed, scan, "provides actual measured properties")
Rel(scan, review, "authorizes next lane step")

@enduml
```
