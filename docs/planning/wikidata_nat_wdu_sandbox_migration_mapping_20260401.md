# Wikidata Nat WDU Sandbox Migration Mapping

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Normalize the provided sandbox page
`User:Nat (WDU)/Sandbox/Fossil fuel industries/Migrate from carbon footprint to GHG emissions`
into the repo's bounded migration-review workflow.

This note treats the sandbox page as:

- a revision-addressable proposal artifact
- a `wiki_revision` source-unit candidate
- a migration-cohort and constraint surface

It does not treat the page as a direct migration executor.

## Source

Current fixture source for this note:

- user-provided page snapshot in the current turn
- canonical page target:
  `https://www.wikidata.org/wiki/User:Nat_(WDU)/Sandbox/Fossil_fuel_industries/Migrate_from_carbon_footprint_to_GHG_emissions`

Current limitation:

- this slice captures the page as a bounded repo fixture
- it does not claim a verified live oldid / revision id yet

## ZKP Frame

### O

Actors and surfaces:

- Nat (WDU) as proposal author
- WikiProject Climate change and ontology discussion as review/governance input
- SensibLaw migration-pack runtime as execution review surface
- repo operators as the final promotion/review decision makers

### R

Required outcome:

- migrate eligible `P5991` statements to `P14143`
- preserve qualifiers, references, and rank intent when appropriate
- isolate exception families instead of flattening them into one wide rewrite

### C

Primary code and artifact surfaces:

- `SensibLaw/docs/planning/wikidata_climate_change_property_migration_protocol_20260327.md`
- `SensibLaw/docs/planning/wikidata_migration_pack_contract_20260328.md`
- `SensibLaw/docs/planning/wiki_revision_source_unit_lattice_admission_20260401.md`
- `SensibLaw/tests/fixtures/wikidata/wiki_revision_nat_wdu_sandbox_p5991_p14143_20260401.json`

### S

Observed page content already supplies:

- an explicit migration goal
- one bounded query anchor
- expected qualifier families
- expected reference families
- open questions about rank and unreconciled populations
- cohort buckets for:
  - business / enterprise / public company
  - other reconciled instance-of classes
  - statements with non-GHG-protocol or missing `determination method (P459)`
  - subjects with no `instance of`
  - subjects with unreconciled `instance of`

### L

Normalized ordering for this sandbox-derived artifact:

1. raw proposal page
2. captured wiki revision source unit
3. mapped migration cohorts and constraints
4. bounded migration-pack cohorts
5. checked-safe / review-only / split-required / held outputs

### P

Proposal:

- use the sandbox page as a first-class proposal artifact
- map its task list into executable migration-pack cohorts
- treat its qualifier/reference lists as expected-shape constraints
- defer live execution until cohorts are materialized and verified

### G

Governance:

- the page can define scope and review questions
- the runtime still decides candidate classification per statement bundle
- no page-level instruction authorizes wide edits by itself

### F

Gap:

- the sandbox page had not yet been normalized into:
  - a first-class `wiki_revision` fixture
  - explicit migration cohorts in repo planning
  - typed expected qualifier/reference constraint sets

## Mapping Into Migration-Pack Protocol

### Cohort A: reconciled business-family subjects

Page bucket:

- 22514 statements on subjects that are instances of:
  - business (`Q4830453`)
  - enterprise (`Q6881511`)
  - public company (`Q891723`)

Repo interpretation:

- first high-volume bounded cohort family
- should become one or more materialized migration packs, not one immediate
  global rewrite

### Cohort B: all other reconciled `instance of`

Page bucket:

- all other reconciled classes outside Cohort A

Repo interpretation:

- secondary cohort family
- likely higher semantic variance
- should be held behind the expected-qualifier and expected-reference checks

### Cohort C: non-GHG-protocol or missing determination method

Page bucket:

- statements where `determination method or standard (P459)` is not GHG
  protocol or is missing

Repo interpretation:

- explicit policy-risk cohort
- should be review-first and likely default to held / review-only until
  stronger equivalence rules exist

### Cohort D: subjects with no `instance of`

Page bucket:

- 1395 statements whose subject lacks `instance of`

Repo interpretation:

- topology / typing-deficit cohort
- should not be mixed into the baseline business-family cohort

### Cohort E: unreconciled `instance of`

Page bucket:

- 142 statements whose `instance of` could not be reconciled

Repo interpretation:

- governance and reconciliation deficit cohort
- should remain explicitly review-only until type normalization is complete

## Expected Qualifier Constraint Set

The sandbox page explicitly calls out these qualifier families:

- `determination method or standard (P459)`
- `object of statement has role (P3831)`
- `point in time (P585)`
- `start time (P580)`
- `end time (P582)`
- `applies to part (P518)`
- `reason for preferred rank (P7452)`

Repo interpretation:

- these become the first expected-shape qualifier allowlist for the sandbox-led
  cohort family
- any additional qualifier family should be surfaced as review pressure, not
  silently dropped

## Expected Reference Constraint Set

The sandbox page explicitly calls out these reference properties in the first
cohort family:

- `reference URL (P854)`
- `archive URL (P1065)`
- `retrieved (P813)`
- `title (P1476)`
- `archive date (P2960)`

Repo interpretation:

- these become the first expected-shape reference family for the sandbox-led
  cohort family
- any additional reference family should be surfaced explicitly

## Rank Handling

The sandbox page asks whether rank needs to be captured.

Repo interpretation:

- yes, rank remains part of the normalized statement bundle
- rank is already preserved by the migration-pack contract
- the page question becomes a review checklist item, not an open implementation
  omission

## ITIL Reading

- service boundary:
  bounded Wikidata migration-review runtime
- change type:
  standard change
- risk:
  low for this slice, because it captures planning intent and fixture state
  rather than widening execution
- backout:
  remove the fixture and mapping note if the cohort interpretation is later
  found to misread the page

## ISO 9000 Reading

Quality objective:

- align public migration intent with deterministic repo-local review artifacts

Quality controls:

- capture source page as a first-class fixture
- preserve qualifier/reference expectations explicitly
- separate cohort families rather than collapsing them

## Six Sigma Reading

Primary defect modes:

- silent qualifier loss
- silent reference loss
- wide-cohort overgeneralization
- unreconciled subject typing mixed into baseline cohorts

Control strategy:

- use page task buckets as explicit variance partitions
- treat unexpected qualifiers/references as surfaced defects, not ignored noise

## C4 / PlantUML

```plantuml
@startuml
title Nat WDU Sandbox To Migration-Pack Mapping

Component(page, "Nat WDU Sandbox Page", "Proposal / cohort definition")
Component(sourceunit, "wiki_revision SourceUnit", "Captured bounded fixture")
Component(mapping, "Cohort Mapping Note", "Normalized cohort and constraint layer")
Component(pack, "MigrationPack Runtime", "Statement-bundle classification")
Component(review, "Checked/Dense Review", "Operator review surfaces")

Rel(page, sourceunit, "captured as")
Rel(sourceunit, mapping, "interpreted through")
Rel(mapping, pack, "defines cohorts and expected constraints")
Rel(pack, review, "emits review artifacts")

@enduml
```
