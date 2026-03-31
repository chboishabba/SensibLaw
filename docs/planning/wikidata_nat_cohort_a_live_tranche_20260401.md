# Wikidata Nat Cohort A Live Tranche

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Promote Nat Cohort A from historical first-slice language into a
live-discovered, repo-pinned tranche workflow.

This slice does not replace the existing historical materialization note. It
adds the first bounded live expansion pass so Nat can search for a genuinely
checked-safe subset without treating live Wikidata as ambient authority.

## Inputs

- `SensibLaw/docs/planning/wikidata_nat_lane_cohort_manifests_20260401.md`
- `SensibLaw/docs/planning/wikidata_nat_cohort_a_review_only_export_20260401.md`
- `SensibLaw/docs/planning/wikidata_migration_pack_contract_20260328.md`
- live WDQS query results constrained to:
  - `P5991`
  - `P31 in {Q4830453, Q6881511, Q891723}`

## ZKP Frame

### O

- Nat lane operators
- ontology-group reviewers
- live WDQS discovery surface
- migration-pack materializer
- repo-pinned tranche artifacts

### R

- run the first bounded live Cohort A expansion pass
- keep live discovery subordinate to pinned repo artifacts
- identify whether the next business-family tranche contains any checked-safe
  subset

### C

- this planning note
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_live_discovery_20260401.json`
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_live_tranche_20260401.json`
- a materialized migration pack under `/tmp/wikidata_nat_cohort_a_live_tranche_20260401`
  for local execution only

### S

- Nat is already at `7 / 8`
- the first historical tranche is entirely `split_required`
- the remaining Nat gate requires a future promoted subset plus post-edit
  verification

### L

1. historical tranche pinned
2. historical tranche classified and exported review-only
3. live discovery constrained to Nat Cohort A
4. bounded live tranche pinned
5. decide whether a checked-safe subset exists
6. verify any future promoted subset

### P

- query live WDQS for a bounded Cohort A candidate set
- materialize only a small tranche from those results
- pin the live-discovery and tranche summary into repo fixtures
- keep progress unchanged unless a genuinely new completion gate is crossed

### G

- live WDQS is discovery only
- repo fixtures remain the governed artifact surface
- no direct edit execution follows from this slice
- no Nat completion claim changes unless a promoted subset is actually found

### F

- close the gap between historical tranche proof and live tranche expansion

## Live Discovery Result

The first live Cohort A pass was bounded to a ranked set drawn from:

- `instance of business (Q4830453)`
- `instance of enterprise (Q6881511)`
- `instance of public company (Q891723)`
- source property `P5991`

Discovery ranking:

- distinct qualifier-property count
- then source-statement count

Pinned discovery shortlist:

- `Q30938280` `Essity` with `14` source statements and `9` distinct qualifier
  properties
- `Q731938` `AstraZeneca` with `91` source statements and `7` distinct
  qualifier properties
- `Q1785637` `Apoteket` with `42` source statements and `7` distinct qualifier
  properties
- `Q738421` `Assa Abloy` with `41` source statements and `7` distinct
  qualifier properties

## Materialized Live Tranche Result

The first pinned live tranche used those four QIDs and produced:

- candidate rows:
  `188`
- checked-safe subset count:
  `0`
- requires review count:
  `188`
- classification bucket counts:
  - `split_required`: `188`
- review CSV rows:
  `188`
- split-plan summary:
  - `plan_count`: `4`
  - `counts_by_status`:
    - `structurally_decomposable`: `4`

Interpretation:

- the first live tranche confirmed the earlier historical tranche result rather
  than softening it
- business-family expansion in that first tranche was structurally
  decompositional
- this first tranche alone did not produce a promoted subset

## Followthrough: Targeted Checked-Safe Hunt

The targeted followthrough now exists in:

- `SensibLaw/docs/planning/wikidata_nat_cohort_a_checked_safe_hunt_20260401.md`
- `SensibLaw/tests/fixtures/wikidata/wikidata_nat_cohort_a_checked_safe_hunt_20260401.json`

Bounded hunt result:

- candidate rows:
  `2`
- checked-safe subset:
  `2`
- bucket counts:
  - `safe_with_reference_transfer`: `2`

Current implication:

- Nat still remains `7 / 8` until post-edit verification is exercised
- the next highest-value step is now explicit:
  run bounded post-edit verification over the discovered checked-safe subset

## ITIL Reading

- service:
  Nat migration-review workflow
- change type:
  standard change
- success condition:
  live discovery is turned into bounded pinned tranche state rather than
  remaining ambient

## ISO 9000 Reading

- quality objective:
  controlled expansion from historical proof slice to live-discovered tranche
- quality result sought:
  reproducible live-to-pinned transition with preserved discovery criteria

## Six Sigma Reading

Observed defect risk:

- live discovery broadens faster than review governance

Control response:

- small ranked tranche, then immediate pinning and classification

## C4 / PlantUML

```plantuml
@startuml
title Nat Cohort A Live Tranche

Component(wdqs, "Live WDQS Discovery", "Bounded candidate probe")
Component(materializer, "Migration Pack Materializer", "Live-to-pinned transition")
Component(tranche, "Pinned Nat Cohort A Live Tranche", "Repo-governed artifact")
Component(review, "Nat Review Workflow", "Classification and export gates")

Rel(wdqs, materializer, "provides bounded QIDs")
Rel(materializer, tranche, "pins tranche summary")
Rel(tranche, review, "feeds next Nat decision")

@enduml
```
