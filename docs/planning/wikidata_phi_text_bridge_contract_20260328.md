# Wikidata Phi Text Bridge Contract (2026-03-28)

## Purpose
Define the bounded bridge between:

- the current structured Wikidata migration-review lane
- a future text-grounded promoted-observation lane

This note does not replace the current migration-pack contract. It defines how
text-aware evidence could be added without breaking the operator-safe baseline.

## Current state
The repo already has a bounded structured migration-review surface for
`P5991 -> P14143`.

Implemented today:
- statement-bundle classification in `MigrationPack`
- `split_required` as a current runtime bucket
- a narrow `suggested_action` field in the migration-pack rows
- OpenRefine export for review/faceting
- first executable bridge scaffolding:
  - schema:
    `schemas/sl.wikidata_phi_text_bridge_case.v1.schema.yaml`
  - runtime:
    `src/ontology/wikidata.py`
  - migration-pack additive fields:
    - `bridge_cases`
    - `text_evidence_refs`
    - `bridge_case_ref`
    - `pressure`
    - `pressure_confidence`
    - `pressure_summary`

Current boundary:
- the structured lane remains the operator baseline
- it is useful for classification/filtering and review support
- it is not yet a final migration executor
- it is not yet reading source text or reasoning over prose

## Main decision
If text understanding is added to this lane, it should enter only as a bounded
upstream evidence surface and must not replace the structured migration lane.

Safe architecture:

`structured statement bundle -> migration review`

plus later:

`text -> anchored observations -> promoted observations`

with `Phi` acting only as the comparison / pressure bridge between those two
promoted surfaces.

Not allowed:
- raw text directly deciding migration action
- text inference bypassing promotion
- text pressure silently overriding structured review output

## Surface split

### 1. Structured surface
Current baseline:

`Wikidata statement bundle -> MigrationPack candidate`

This remains the first authority for:
- qualifier/reference structure
- slot multiplicity
- revision-window drift
- current review bucket
- current suggested reviewer action

### 2. Text-grounded surface
Future bounded lane:

`source text -> anchored spans -> candidate observations -> promoted observations`

Safe requirements:
- bounded sources only
- explicit span anchoring
- no hidden inference layer
- promotion required before bridge use

## Bridge contract
The bridge should be typed as one bounded review object:

`BridgeCase = { structured_bundle, text_observations, comparison, pressure }`

### `structured_bundle`
Required fields:
- `candidate_id`
- `entity_qid`
- `slot_id`
- `statement_index`
- `classification`
- `suggested_action`
- `claim_bundle_before`
- `claim_bundle_after`

This is a reference into the current migration-pack surface, not a new truth
source.

### `text_observations`
The text side must reference only promoted observation rows.

Required fields:
- `observation_ref`
- `source_ref`
- `anchors`
- `subject`
- `predicate`
- `object`
- `qualifiers`
- `promotion_status`

The bridge should reject non-promoted text observations.

### `comparison`
This is the bounded `Phi` comparison surface.

Required outputs:
- `alignment`
- `conflicts`
- `missing_dimensions`
- `comparison_summary`

Interpretation:
- `alignment` = where structured and text-grounded surfaces support the same
  reading
- `conflicts` = where they point in different directions
- `missing_dimensions` = where one surface names a time/scope distinction that
  the other does not

### `pressure`
This is the only place text should influence migration review.

Allowed values:
- `reinforce`
- `split_pressure`
- `contradiction`
- `abstain`

Meaning:
- `reinforce`
  - text evidence supports the current structured reading
- `split_pressure`
  - text evidence suggests the current structured bundle compresses more than
    one time/scope/value distinction
- `contradiction`
  - text evidence pulls against the current structured reading
- `abstain`
  - text evidence is insufficient to support any pressure claim

## Governance rule
Text pressure does not directly set final migration action.

Safe rule:
- structured lane remains the baseline
- bridge output may add:
  - evidence
  - review pressure
  - more precise explanation
- bridge output may justify upgrading a coarse structured bucket into a more
  specific review action
- bridge output must not auto-execute edits

## Intended first use
The first bounded use should target the current hardest family:
- temporal / multi-value `P5991` rows

This is the exact place where:
- the structured lane already catches risk
- the current output is still too coarse
- text evidence could help distinguish:
  - true split-required cases
  - cases that merely need source retention
  - cases that remain unresolved even after text review

## Integration target
The first safe integration point is additive metadata on current migration-pack
rows.

Bounded future fields:
- `text_evidence_refs`
- `bridge_case_ref`
- `pressure`
- `pressure_confidence`
- `pressure_summary`

Safe interpretation:
- these fields refine review support
- they do not replace `classification`
- they do not make the lane a final migration executor

## Immediate implementation goal
Do not start with generic text understanding.

Start with:
1. one bounded bridge schema
2. one pressure grammar
3. one temporal/multi-value climate case family
4. one review-facing additive output path

That keeps the lane aligned with existing repo doctrine:
- promotion before truth-bearing use
- `Phi` as comparison, not oracle
- operator review before execution

## First bounded producer target
The next real producer should stay narrow and revision-locked rather than
pretending to be generic source-text understanding.

Chosen target:
- revision-locked climate text source
- explicit year/value climate lines only
- one emitted `sl.observation_claim.contract.v1` payload
- direct bridge attachment into the existing migration-pack runtime

Boundary:
- no live text fetch inside the producer
- no open-ended semantic parsing
- abstain when a line does not match the bounded year/value climate pattern
- keep output limited to anchored annual-emissions-style observations

## First executable slice
The first runtime slice is additive to `MigrationPack`, not a separate
replacement report.

Implemented additive fields on each candidate row:
- `text_evidence_refs`
- `bridge_case_ref`
- `pressure`
- `pressure_confidence`
- `pressure_summary`

Implemented top-level field on the migration pack:
- `bridge_cases`

Current default behavior:
- when no promoted text observations are provided:
  - `bridge_cases = []`
  - candidate `text_evidence_refs = []`
  - candidate `bridge_case_ref = null`
  - candidate `pressure = null`
  - candidate `pressure_confidence = null`
  - candidate `pressure_summary = null`

That preserves the current structured baseline while making the bridge surface
machine-visible for later bounded runs.

## First real producer
The first real producer for bridge observations should be the existing
Observation/Claim contract, not a new one-off text format.

Safe first producer:
- input contract:
  `schemas/sl.observation_claim.contract.v1.schema.yaml`
- bounded producer rule:
  convert verified/adjudicated observation/claim rows into bridge observations
  only when they remain source-anchored and claim posture is supportive

Interpretation:
- this keeps the text side inside an existing promoted/checked SL seam
- it avoids inventing a migration-specific text payload
- it lets the bridge consume a real producer before any wider text pipeline is
  attempted

Immediate next executable followthrough:
- add one bounded climate producer that emits
  `sl.observation_claim.contract.v1` rows from revision-locked text sources for
  temporal/multi-value `P5991` cases
- feed that payload directly into
  `attach_wikidata_phi_text_bridge_from_observation_claim(...)`

Implemented bounded climate producer/runtime slice:
- source schema:
  `schemas/sl.wikidata.climate_text_source.v1.schema.yaml`
- runtime helpers in `src/ontology/wikidata.py`:
  - `build_observation_claim_payload_from_revision_locked_climate_text_sources(...)`
  - `attach_wikidata_phi_text_bridge_from_revision_locked_climate_text(...)`
- materializer hook in:
  `scripts/materialize_wikidata_migration_pack.py`
  - `--climate-text-source`
  - `--climate-observation-claim-output`

Current boundary of that producer:
- revision-locked input only
- explicit year/value climate lines only
- annual-emissions-style observations only
- abstain on unmatched lines

First real non-fixture artifact/result:
- artifact:
  `data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json`
- source family:
  official Akademiska Hus annual reports for 2018, 2019, and 2020
- observed bridge outcome:
  before the temporal matcher fix, the artifact yielded `3` promoted
  observations / claims and drove `contradiction` pressure on all `24`
  current `Q10403939` candidates
- interpretation:
  that showed the bridge was conservative, but also too coarse about explicit
  year mismatch

Implemented runtime promotion:
- period-aware gating is now active
- if text observations fall outside the structured bundle's temporal slice,
  value mismatch now surfaces as temporal-dimension pressure rather than hard
  contradiction
- re-running the real `Q10403939` artifact now yields `split_pressure` on all
  `24` candidates

Implemented runtime promotion:
- simple scope-tag carriage now runs through the generic source-unit ->
  observation-claim -> bridge path
- bridge comparison now distinguishes temporal mismatch from explicit
  scope-dimension mismatch while keeping the same bounded pressure grammar
- scope tags remain additive evidence only; they do not bypass the structured
  lane or change migration action directly

Generalization boundary:
- the system should now be understood as source-unit driven, not PDF-driven
- `sl.wikidata.climate_text_source.v1` remains a supported climate-specific
  legacy input surface
- the next reusable runtime surface is a generic revision-locked
  `sl.source_unit.v1` contract plus a `SourceUnitAdapter` path in
  `src/ontology/wikidata.py`
- first supported source-unit types should stay narrow:
  - PDF snapshot text
  - HTML snapshot text
  - bounded wiki revision text
- this is a source-capture generalization only; it must not widen the bridge
  semantics or weaken the current promotion/anchoring requirements

Current executable status:
- implemented adapter in:
  `src/ontology/wikidata.py`
- runtime entry points:
  - `extract_phi_text_observations_from_observation_claim_payload(...)`
  - `attach_wikidata_phi_text_bridge_from_observation_claim(...)`
- current rule:
  - `verified` / `adjudicated` active observations plus supportive claims are
    lifted into bridge observations
  - the bridge still remains additive to migration-pack output
