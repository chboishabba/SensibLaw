# Wiki Revision SourceUnit Lattice Admission

Date: 2026-04-01

## Change Class

Standard change.

## Purpose

Record the first explicit admission rule for revision-locked Wikipedia text into
the existing source-unit to observation-claim to Phi bridge path.

This note does not promote Wikipedia prose directly into semantic truth. It
defines how one captured revision can enter the repo's governed evidence
lattice as a bounded artifact.

## Problem

The repo already has:

- a generic `sl.source_unit.v1` contract
- a bounded Observation/Claim extraction path
- a bounded Phi bridge for Wikidata migration review

But the wiki-assisted quality discussion still lacked one explicit planning
artifact stating that a captured `wiki_revision` can be admitted into the same
lattice rather than being treated as permanently external or informal.

## Requirement

One revision-locked wiki artifact must be able to move through:

1. source captured
2. revision locked
3. anchor extracted
4. observation typed
5. claim linked
6. pressure compared
7. review passed
8. promoted or held

For this slice, we only need to prove admission through the first six stages
and preserve the governance rule that text remains upstream evidence, not direct
migration authority.

## Boundary

Admitted source type:

- `sl.source_unit.v1`
  - `revision.retrieval_method = wiki_revision`
  - `origin.source_type = wiki`

Bounded downstream path:

- `build_observation_claim_payload_from_source_units(...)`
- `attach_wikidata_phi_text_bridge_from_source_units(...)`

Not in scope:

- open-ended article parsing
- live fetch
- direct migration execution
- replacing the structured Wikidata lane

## First pinned fixture

The first pinned admission fixture is:

- `SensibLaw/tests/fixtures/wikidata/wiki_revision_source_unit_fixture_20260401.json`

It should be read as:

- one captured Wikipedia revision
- one bounded text excerpt
- one extractable emissions-style observation family
- one review comparison against the existing migration lane

## Lattice interpretation

For wiki-derived inputs, the normalized meaning is:

- raw:
  captured revision exists but has not yet been bounded into extractable spans
- bounded:
  specific revision, source unit, and excerpt are pinned
- checked:
  extraction path and comparison path run deterministically and pass contract
  validation
- promoted:
  only after review accepts the extracted claim as fit for truth-bearing use
- held:
  evidence is preserved but not promoted because comparison pressure or policy
  says stop
- contradicted:
  bridge or downstream review finds direct conflict with the structured lane
- review-only:
  evidence is useful for operator interpretation but not yet promotion-ready

## Governance

- Wikipedia revision text is admissible only after capture and revision locking
- the structured Wikidata lane remains the baseline authority for migration
  classification
- text enters only as additive evidence and pressure
- no raw prose to migration action shortcut
- no live authority claim from Wikipedia as a platform

## Quality Gate

Run from `SensibLaw/`:

- `../.venv/bin/python -m pytest -q tests/test_wikidata_projection.py`

The slice is successful if the pinned fixture:

- validates as `sl.source_unit.v1`
- emits Observation/Claim rows through the existing extractor
- enters the Phi bridge through the existing source-unit path
- yields bounded review pressure without widening bridge semantics

## C4 / PlantUML

```plantuml
@startuml
title Wiki Revision SourceUnit Lattice Admission

Component(wiki, "Captured Wiki Revision", "Revision-locked upstream artifact")
Component(sourceunit, "sl.source_unit.v1", "Normalized admission boundary")
Component(obs, "ObservationClaim", "Anchored extraction")
Component(phi, "Phi Bridge", "Pressure/comparison only")
Component(migration, "MigrationPack", "Structured baseline")

Rel(wiki, sourceunit, "captured as")
Rel(sourceunit, obs, "extracts to")
Rel(obs, phi, "feeds")
Rel(migration, phi, "compares against")

@enduml
```
