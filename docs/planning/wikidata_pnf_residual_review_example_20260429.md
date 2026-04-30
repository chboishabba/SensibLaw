# Wikidata PNF / Residual Review Example

Date: 2026-04-29

## Purpose

Provide one concrete bounded example that maps a real Wikidata climate-review
case through the newer canonical-text, predicate-normal-form, and residual
comparison framing.

This note exists because the repo already has:

- a real bounded `P5991 -> P14143` migration pack
- a real revision-locked climate text artifact
- a real bridge result over that artifact

but the PNF/residual interpretation has been implicit across several docs
rather than written down as one end-to-end review example.

## Boundary

This note mixes two things deliberately and names the difference:

- **already executable artifacts**
  - migration pack rows
  - split axes
  - text bridge pressure result
- **current interpretation layer**
  - how the same case should be read through the newer PNF/residual carrier

So this is a bounded docs-first review note, not a claim that one CLI command
already emits this exact end-to-end residual object for the Wikidata lane.

## Current real artifact set

Primary artifacts:

- migration-pack manifest:
  `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/manifest.json`
- migration pack:
  `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json`
- revision-locked climate text source:
  `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json`

Key status references:

- `SensibLaw/docs/wikidata_working_group_status.md`
- `SensibLaw/docs/planning/wikidata_phi_text_bridge_contract_20260328.md`

Relevant runtime surfaces:

- canonical text / body-qualified units:
  `SensibLaw/src/ingestion/media_adapter.py`
- shared reducer body-qualified predicate projection:
  `SensibLaw/src/sensiblaw/interfaces/shared_reducer.py`
- predicate carrier + residual lattice:
  `SensibLaw/src/text/residual_lattice.py`

## Actual demonstrator inputs

The runtime command does not consume three abstract ideas. It consumes three
concrete JSON payloads:

1. **migration pack**
   - schema: `sl.wikidata_migration_pack.v1`
   - file:
     `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json`
   - runtime use:
     `build_wikidata_climate_review_demonstrator(...)` reads
     `candidates[*]` and uses fields such as:
     - `candidate_id`
     - `entity_qid`
     - `classification`
     - `action`
     - `split_axes`
     - `claim_bundle_before`
     - `claim_bundle_after`

2. **review packet**
   - schema: `sl.wikidata_review_packet.v0_1`
   - file:
     `SensibLaw/tests/fixtures/wikidata/wikidata_nat_review_packet_20260401.json`
   - runtime use:
     `_select_demonstrator_candidates(...)` uses it only as bounded selection
     / context, mainly:
     - `review_entity_qid`
     - `split_review_context.source_candidate_ids`
     - `split_review_context.split_plan_id`

3. **climate text source**
   - schema: `sl.wikidata.climate_text_source.v1`
   - file:
     `SensibLaw/data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json`
   - runtime use:
     `build_observation_claim_payload_from_revision_locked_climate_text_sources(...)`
     adapts legacy `sources[*]` rows into canonical source units, then extracts
     climate rows using:
     - `source_id`
     - `entity_qid`
     - `source_unit_id`
     - `revision_id`
     - `revision_timestamp`
     - `text`

So the actual bounded runtime is:

- migration-pack rows provide the structured candidate surface
- review-packet context selects which rows to inspect
- climate-text rows provide revision-locked text evidence that becomes
  observations / claims / evidence links

## The case

Entity:

- `Q10403939` (`Akademiska Hus`)

Current structured migration-pack truth:

- current candidate rows for this entity: `24`
- current classification: `split_required = 24`
- current action: `split = 24`

Current split axes on those rows include:

- `__value__`
- `P3831`
- `P518`
- `P580`
- `P582`

So the structured lane is already saying:

- this is not a checked-safe direct migration case
- the slot carries multiple independent dimensions
- the right bounded posture is review/split, not direct promotion

Current text-bridge truth:

- the revision-locked Akademiska Hus climate artifact yields `3` promoted
  observations / claims
- after temporal gating, those observations drive `split_pressure` on all
  `24` current `Q10403939` candidates

Current interpretation recorded elsewhere:

- this is the conservative result because the text slice is older scope-1
  evidence while the current structured bundle is newer multi-scope data
- that is a dimensional mismatch, not a hard contradiction

## Step 1: signal layer

There are at least two candidate-signal sources here:

1. the structured `P5991` bundle itself
2. the revision-locked climate text artifact

Possible broader signal sources could also include:

- LLM suggestions
- ontology checks
- external ontology mappings

But none of those should decide action directly.

At this stage the useful claim is only:

- there is a potentially relevant emissions case
- it is structurally nontrivial
- it deserves a bounded review artifact

That is a `candidate-only` state, not an edit-ready state.

## Step 2: body-qualified source discipline

The newer ingest/reducer path matters before any comparison logic:

- PDF/text content is adapted into canonical text
- units carry `body_qualified` metadata
- predicate projection only runs over body-qualified units

This reduces the chance that wrapper text, citation panels, browser chrome, or
other PDF noise silently becomes semantic evidence.

For this lane, that means the text-side comparison surface is more likely to be
about actual emissions statements rather than document furniture.

## Step 3: PNF reading of the same case

The current runtime does not yet emit this exact Wikidata migration case as one
explicit `PredicatePNF` bundle. But the newer carrier gives the right way to
read it.

### Structured side

If read through the current typed carrier, the structured side is not "one
emissions fact". It is closer to:

- predicate:
  annual / reported emissions amount
- subject:
  `Q10403939`
- value surface:
  multi-valued
- qualifier / dimension surface:
  - scope-like variation (`P518`)
  - method/standard variation (`P3831`)
  - time variation (`P580`, `P582`)

The key point is not the exact normalized predicate label. The key point is:

- the structured candidate is already dimension-rich
- those dimensions are what make the row non-promotable as a 1:1 migration

### Text side

The revision-locked climate text source is narrower. It is closer to:

- predicate:
  emissions amount
- subject:
  `Q10403939`
- value:
  one bounded annual figure
- qualifier surface:
  - explicit year
  - explicit `scope 1`
- wrapper state:
  evidence-bearing, but still only useful through the governed bridge

So the text side is not "the truth that replaces the structured lane". It is a
more specific, narrower slice.

## Step 4: residual reading

This is where the newer residual lattice helps explain the correct action.

The important residual question is not:

- did text mention emissions?

The important residual question is:

- how does the narrower text-side slice meet the broader structured candidate?

For this case, the right reading is:

- **not `EXACT`**
  - because the structured candidate compresses many values and dimensions
- **not hard `CONTRADICTION`**
  - because older scope-1 evidence can coexist with newer multi-scope
    structured data
- **closer to `PARTIAL` / dimensional mismatch**
  - because the text meets part of the structure but does not resolve the full
    slot cleanly

That is why the current bridge result sensibly lands on:

- `split_pressure`

rather than:

- `reinforce`
- or `contradiction`

In other words, the bridge is not saying:

- "migrate this now"

It is saying:

- "the evidence supports the view that this bundle is compressing several
  dimensions and should stay in a split/review posture"

## Step 5: review bucket outcome

For this concrete case, the bucket path is:

1. `candidate-only`
   - raw structured/text signals exist
2. `reviewable`
   - the case is bounded, revision-locked, and artifact-backed
3. `held`
   - it remains `split_required` / review-first rather than promotable

So this example does **not** end in `promotable`.

That matters because it shows the real value of the newer layer:

- it makes incompleteness and dimensional mismatch explicit
- it refuses to collapse that mismatch into a false direct migration

## Why this assists OCTF directly

This example is useful for OCTF because it demonstrates a stronger boundary
than generic "human in the loop" review:

- candidate signals are typed and non-authoritative
- source evidence is filtered through bounded body-qualified substrate rules
- comparison can express:
  - exact support
  - partial support
  - no typed meet
  - contradiction
- bounded review artifacts can therefore say not only "there may be a
  problem here" but also:
  - what kind of mismatch this is
  - whether it is promotable
  - or whether it should stay held

For `Q10403939`, the answer is:

- reviewable: yes
- promotable to direct migration: no
- correct current posture: held split/review pressure

## What this does not claim

- this is not a claim that the Wikidata lane now has full automatic text-side
  residual evaluation over all migration candidates
- this is not a claim that PNF alone decides Wikidata edits
- this is not a claim that every `split_pressure` case should become a split
  plan automatically

The narrower claim is:

- the newer canonical-text, PNF, and residual work gives the repo a much
  cleaner way to explain why a real Wikidata climate case should remain a
  bounded review object rather than collapsing prematurely into action

## Runtime companion

This note now has a bounded runtime companion:

- `../.venv/bin/python -m cli.__main__ wikidata climate-review-demonstrator \
  --migration-pack data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/migration_pack.json \
  --climate-text data/ontology/wikidata_migration_packs/p5991_p14143_climate_pilot_20260328/climate_text_source_q10403939_akademiska_hus_scope1_2018_2020.json \
  --review-packet tests/fixtures/wikidata/wikidata_nat_review_packet_20260401.json \
  --output /tmp/q10403939_climate_review_demonstrator.json`

That command materializes the same four-step object this note has been
describing:

- bounded candidate change surface
- text-side predicate carrier
- residual/completeness surface
- final review disposition

If you want the same runtime as one compact diagram, use:

- `SensibLaw/docs/planning/wikidata_climate_review_demonstrator_flow_20260429.puml`
